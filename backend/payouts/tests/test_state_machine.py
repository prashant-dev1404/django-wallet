import pytest
from payouts.models import Payout
from payouts.state_machine import transition_to, IllegalStateTransition
from ledger.tests.factories import MerchantFactory, BankAccountFactory


@pytest.fixture
def pending_payout(db):
    merchant = MerchantFactory()
    bank = BankAccountFactory(merchant=merchant)
    return Payout.objects.create(
        merchant=merchant,
        bank_account=bank,
        amount_paise=5000,
        status="PENDING",
    )


@pytest.mark.django_db
def test_pending_to_processing_allowed(pending_payout):
    transition_to(pending_payout, "PROCESSING")
    assert pending_payout.status == "PROCESSING"


@pytest.mark.django_db
def test_processing_to_completed_allowed(pending_payout):
    transition_to(pending_payout, "PROCESSING")
    transition_to(pending_payout, "COMPLETED")
    assert pending_payout.status == "COMPLETED"


@pytest.mark.django_db
def test_processing_to_failed_allowed(pending_payout):
    transition_to(pending_payout, "PROCESSING")
    transition_to(pending_payout, "FAILED")
    assert pending_payout.status == "FAILED"


@pytest.mark.django_db
def test_processing_to_pending_allowed_for_retry(pending_payout):
    transition_to(pending_payout, "PROCESSING")
    transition_to(pending_payout, "PENDING")
    assert pending_payout.status == "PENDING"


@pytest.mark.django_db
def test_completed_to_anything_blocked(pending_payout):
    transition_to(pending_payout, "PROCESSING")
    transition_to(pending_payout, "COMPLETED")
    for target in ["PENDING", "PROCESSING", "FAILED"]:
        with pytest.raises(IllegalStateTransition):
            transition_to(pending_payout, target)


@pytest.mark.django_db
def test_failed_to_completed_blocked(pending_payout):
    transition_to(pending_payout, "PROCESSING")
    transition_to(pending_payout, "FAILED")
    with pytest.raises(IllegalStateTransition):
        transition_to(pending_payout, "COMPLETED")


@pytest.mark.django_db
def test_failed_to_anything_blocked(pending_payout):
    transition_to(pending_payout, "PROCESSING")
    transition_to(pending_payout, "FAILED")
    for target in ["PENDING", "PROCESSING", "COMPLETED"]:
        with pytest.raises(IllegalStateTransition):
            transition_to(pending_payout, target)


@pytest.mark.django_db
def test_pending_to_completed_blocked(pending_payout):
    with pytest.raises(IllegalStateTransition):
        transition_to(pending_payout, "COMPLETED")


@pytest.mark.django_db
def test_pending_to_failed_blocked(pending_payout):
    with pytest.raises(IllegalStateTransition):
        transition_to(pending_payout, "FAILED")


@pytest.mark.django_db
def test_transition_persists_to_db(pending_payout):
    transition_to(pending_payout, "PROCESSING")
    refreshed = Payout.objects.get(id=pending_payout.id)
    assert refreshed.status == "PROCESSING"


@pytest.mark.django_db
def test_transition_only_updates_status_field(pending_payout):
    pending_payout.failure_reason = "should not be saved"
    transition_to(pending_payout, "PROCESSING")
    refreshed = Payout.objects.get(id=pending_payout.id)
    assert refreshed.failure_reason == ""  # not saved — update_fields only covers status
