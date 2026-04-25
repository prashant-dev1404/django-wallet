from uuid import UUID
from django.db import transaction
from django.db.models import Sum, Case, When, F, Value, BigIntegerField
from django.db.models.functions import Coalesce
from .models import Merchant, LedgerEntry


def get_balance(merchant_id: UUID) -> int:
    """
    Returns the merchant's current balance in paise.

    Uses Django ORM aggregation. Database does the math, never Python.
    No caching: balance can change at any moment.
    """
    result = LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
        balance=Coalesce(
            Sum(Case(
                When(entry_type='CREDIT', then=F('amount_paise')),
                When(entry_type='DEBIT', then=-F('amount_paise')),
                output_field=BigIntegerField(),
            )),
            Value(0),
            output_field=BigIntegerField(),
        )
    )
    return result['balance']


def get_balance_for_update(merchant_id: UUID) -> int:
    """
    Same as get_balance but acquires a row-level lock on the merchant's ledger rows.
    MUST be called inside transaction.atomic().

    select_for_update() requires an active transaction.
    """
    # First, lock the rows
    list(LedgerEntry.objects.filter(merchant_id=merchant_id)
         .select_for_update()
         .values_list('id', flat=True))

    # Then aggregate as in get_balance()
    result = LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
        balance=Coalesce(
            Sum(Case(
                When(entry_type='CREDIT', then=F('amount_paise')),
                When(entry_type='DEBIT', then=-F('amount_paise')),
                output_field=BigIntegerField(),
            )),
            Value(0),
            output_field=BigIntegerField(),
        )
    )
    return result['balance']


def create_ledger_entry(
    merchant: Merchant,
    entry_type: str,
    amount_paise: int,
    reference_type: str,
    reference_id: UUID = None,
    description: str = ""
) -> LedgerEntry:
    """
    Create a new ledger entry.

    Args:
        merchant: The merchant for this entry
        entry_type: 'CREDIT' or 'DEBIT'
        amount_paise: Amount in paise (always positive)
        reference_type: Type of transaction (e.g., 'CUSTOMER_PAYMENT', 'PAYOUT_HOLD')
        reference_id: Optional UUID reference to related object
        description: Optional description

    Returns:
        The created LedgerEntry instance
    """
    if entry_type not in ['CREDIT', 'DEBIT']:
        raise ValueError(f"Invalid entry_type: {entry_type}")

    if amount_paise <= 0:
        raise ValueError("amount_paise must be positive")

    return LedgerEntry.objects.create(
        merchant=merchant,
        entry_type=entry_type,
        amount_paise=amount_paise,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
    )


def get_merchant_balance_summary(merchant_id: UUID) -> dict:
    """
    Get comprehensive balance information for a merchant.

    held_paise is the sum of payout amounts in PENDING/PROCESSING status.
    It is display-only — the actual debit (PAYOUT_HOLD) is already in the ledger
    and reflected in available_paise. Do not subtract it again.
    """
    # Lazy import avoids circular dependency (payouts imports ledger)
    from payouts.models import Payout

    available_balance = get_balance(merchant_id)

    totals = LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
        total_credits=Coalesce(
            Sum(Case(When(entry_type='CREDIT', then=F('amount_paise')), output_field=BigIntegerField())),
            Value(0), output_field=BigIntegerField()
        ),
        total_debits=Coalesce(
            Sum(Case(When(entry_type='DEBIT', then=F('amount_paise')), output_field=BigIntegerField())),
            Value(0), output_field=BigIntegerField()
        )
    )

    held_result = Payout.objects.filter(
        merchant_id=merchant_id,
        status__in=[Payout.PENDING, Payout.PROCESSING],
    ).aggregate(
        total=Coalesce(Sum('amount_paise'), Value(0), output_field=BigIntegerField())
    )

    return {
        "available_paise": available_balance,
        "held_paise": held_result['total'],
        "total_credited_paise": totals['total_credits'],
        "total_debited_paise": totals['total_debits'],
    }
