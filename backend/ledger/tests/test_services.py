import pytest
from django.db import transaction
from django.core.management import call_command
from ledger.models import LedgerEntry
from ledger.services import get_balance, get_balance_for_update, create_ledger_entry
from ledger.tests.factories import MerchantFactory, LedgerEntryFactory


@pytest.mark.django_db
def test_balance_empty_merchant_returns_zero():
    merchant = MerchantFactory()
    assert get_balance(merchant.id) == 0


@pytest.mark.django_db
def test_balance_sums_credits_minus_debits():
    merchant = MerchantFactory()
    LedgerEntryFactory(merchant=merchant, entry_type="CREDIT", amount_paise=10000)
    LedgerEntryFactory(merchant=merchant, entry_type="CREDIT", amount_paise=5000)
    LedgerEntryFactory(merchant=merchant, entry_type="DEBIT", amount_paise=3000)
    assert get_balance(merchant.id) == 12000


@pytest.mark.django_db(transaction=True)
def test_balance_for_update_requires_transaction():
    from django.db.transaction import TransactionManagementError
    merchant = MerchantFactory()
    LedgerEntryFactory(merchant=merchant, entry_type="CREDIT", amount_paise=5000)
    # Outside transaction.atomic(), select_for_update() must raise
    with pytest.raises(TransactionManagementError):
        get_balance_for_update(merchant.id)


@pytest.mark.django_db
def test_ledger_entry_is_append_only():
    merchant = MerchantFactory()
    entry = LedgerEntryFactory(merchant=merchant, entry_type="CREDIT", amount_paise=5000)
    entry.amount_paise = 9999
    with pytest.raises(ValueError, match="append-only"):
        entry.save()


@pytest.mark.django_db
def test_credit_rejects_zero_or_negative():
    merchant = MerchantFactory()
    with pytest.raises(ValueError):
        create_ledger_entry(merchant, "CREDIT", 0, "TEST")
    with pytest.raises(ValueError):
        create_ledger_entry(merchant, "CREDIT", -1, "TEST")


@pytest.mark.django_db
def test_credit_creates_entry_with_correct_fields():
    import uuid
    merchant = MerchantFactory()
    ref_id = uuid.uuid4()
    entry = create_ledger_entry(
        merchant,
        "CREDIT",
        10000,
        "CUSTOMER_PAYMENT",
        reference_id=ref_id,
        description="test deposit",
    )
    assert entry.entry_type == "CREDIT"
    assert entry.amount_paise == 10000
    assert entry.reference_type == "CUSTOMER_PAYMENT"
    assert entry.reference_id == ref_id
    assert entry.description == "test deposit"
    assert entry.created_at is not None
    assert LedgerEntry.objects.filter(id=entry.id).exists()
