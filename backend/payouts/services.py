from uuid import UUID
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Payout
from .state_machine import transition_to
from ledger.models import Merchant, BankAccount
from ledger.services import get_balance_for_update, create_ledger_entry


class InsufficientBalance(Exception):
    """Raised when merchant doesn't have enough balance for payout."""
    def __init__(self, available_balance: int, requested_amount: int):
        self.available_balance = available_balance
        self.requested_amount = requested_amount
        super().__init__(f"Insufficient balance: {available_balance} paise available, {requested_amount} paise requested")


def _validate_amount(amount_paise: int) -> None:
    """Validate payout amount."""
    if amount_paise <= 0:
        raise ValidationError("Amount must be positive")
    if amount_paise > 1000000000:  # 10 million rupees in paise
        raise ValidationError("Amount too large")


def _validate_bank_account_belongs_to_merchant(bank_account_id: UUID, merchant_id: UUID) -> BankAccount:
    """Validate bank account exists and belongs to merchant."""
    try:
        bank_account = BankAccount.objects.get(id=bank_account_id)
    except BankAccount.DoesNotExist:
        raise ValidationError("Bank account not found")

    if bank_account.merchant_id != merchant_id:
        raise ValidationError("Bank account does not belong to merchant")

    return bank_account


def create_payout(
    merchant_id: UUID,
    bank_account_id: UUID,
    amount_paise: int,
) -> Payout:
    """
    Create a new payout request.

    This function assumes the idempotency key has been recorded;
    it focuses on the lock-check-debit-create flow.

    Args:
        merchant_id: UUID of the merchant
        bank_account_id: UUID of the bank account
        amount_paise: Amount to payout in paise

    Returns:
        The created Payout instance (in PENDING status)

    Raises:
        InsufficientBalance: If merchant doesn't have enough balance
        ValidationError: For invalid inputs
    """
    _validate_amount(amount_paise)
    bank_account = _validate_bank_account_belongs_to_merchant(bank_account_id, merchant_id)

    with transaction.atomic():
        # 1. Lock the merchant's ledger rows and get balance
        balance = get_balance_for_update(merchant_id)

        # 2. Check sufficient funds
        if balance < amount_paise:
            raise InsufficientBalance(balance, amount_paise)

        # 3. Create the payout (PENDING)
        payout = Payout.objects.create(
            merchant_id=merchant_id,
            bank_account=bank_account,
            amount_paise=amount_paise,
            status="PENDING",
        )

        # 4. Create the hold as a DEBIT ledger entry, atomically
        create_ledger_entry(
            merchant=bank_account.merchant,
            entry_type="DEBIT",
            amount_paise=amount_paise,
            reference_type="PAYOUT_HOLD",
            reference_id=payout.id,
            description=f"Hold for payout {payout.id}",
        )

    return payout


def process_payout(payout_id: UUID) -> None:
    """
    Process a payout (move from PENDING to PROCESSING).

    This would typically be called by a background worker.
    """
    try:
        payout = Payout.objects.select_for_update().get(id=payout_id)
        transition_to(payout, "PROCESSING")
        payout.save()
    except Payout.DoesNotExist:
        raise ValidationError("Payout not found")


def complete_payout(payout_id: UUID) -> None:
    """
    Complete a payout (move from PROCESSING to COMPLETED).

    This would typically be called by a background worker after
    successful bank transfer.
    """
    try:
        payout = Payout.objects.select_for_update().get(id=payout_id)
        transition_to(payout, "COMPLETED")
        payout.save()
    except Payout.DoesNotExist:
        raise ValidationError("Payout not found")


def fail_payout(payout_id: UUID) -> None:
    """Fail a payout and release its hold via a CREDIT refund entry."""
    with transaction.atomic():
        try:
            payout = Payout.objects.select_for_update().get(id=payout_id)
            transition_to(payout, "FAILED")
            create_ledger_entry(
                merchant=payout.merchant,
                entry_type="CREDIT",
                amount_paise=payout.amount_paise,
                reference_type="PAYOUT_REFUND",
                reference_id=payout.id,
                description=f"Refund for failed payout {payout.id}",
            )
        except Payout.DoesNotExist:
            raise ValidationError("Payout not found")


def pickup_pending_payouts(limit: int = 50) -> list:
    """
    Transition PENDING payouts to PROCESSING and return their IDs.

    Uses skip_locked so multiple workers pick disjoint rows. The simulated
    bank call happens OUTSIDE this function (after the transaction commits).
    """
    picked_ids = []
    with transaction.atomic():
        candidates = (
            Payout.objects
            .select_for_update(skip_locked=True)
            .filter(status=Payout.PENDING)
            .filter(
                Q(processing_started_at__isnull=True) |
                Q(processing_started_at__lte=timezone.now())
            )
            .order_by("created_at")[:limit]
        )
        for payout in candidates:
            transition_to(payout, Payout.PROCESSING)
            payout.processing_started_at = timezone.now()
            payout.attempt_count += 1
            payout.save(update_fields=["processing_started_at", "attempt_count", "updated_at"])
            picked_ids.append(payout.id)
    return picked_ids


def settle_payout(payout_id: UUID, outcome: str) -> None:
    """
    Record the bank settlement outcome. Called OUTSIDE any open transaction.

    outcome: "success" → COMPLETED, no ledger change (hold is already final).
             "failure" → FAILED + CREDIT refund entry, both in one atomic block.
    """
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)
        if outcome == "success":
            transition_to(payout, Payout.COMPLETED)
        elif outcome == "failure":
            transition_to(payout, Payout.FAILED)
            payout.failure_reason = "simulated bank failure"
            payout.save(update_fields=["failure_reason", "updated_at"])
            create_ledger_entry(
                merchant=payout.merchant,
                entry_type="CREDIT",
                amount_paise=payout.amount_paise,
                reference_type="PAYOUT_REFUND",
                reference_id=payout.id,
                description=f"Refund for failed payout {payout.id}",
            )


def retry_or_fail(payout_id: UUID) -> None:
    """
    Handle a payout stuck in PROCESSING.

    attempt_count < 3 → back to PENDING with exponential backoff (5s, 10s, 20s).
    attempt_count >= 3 → FAILED with CREDIT refund, both atomic.
    """
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)
        if payout.status != Payout.PROCESSING:
            return  # already handled by another worker

        if payout.attempt_count < 3:
            backoff_seconds = 5 * (2 ** payout.attempt_count)  # 5, 10, 20
            transition_to(payout, Payout.PENDING)
            payout.processing_started_at = timezone.now() + timedelta(seconds=backoff_seconds)
            payout.save(update_fields=["processing_started_at", "updated_at"])
        else:
            transition_to(payout, Payout.FAILED)
            payout.failure_reason = "max retries exhausted"
            payout.save(update_fields=["failure_reason", "updated_at"])
            create_ledger_entry(
                merchant=payout.merchant,
                entry_type="CREDIT",
                amount_paise=payout.amount_paise,
                reference_type="PAYOUT_REFUND",
                reference_id=payout.id,
                description=f"Refund for exhausted payout {payout.id}",
            )
