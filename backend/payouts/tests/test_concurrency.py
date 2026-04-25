import pytest
from threading import Thread, Barrier
from django.db import close_old_connections
from payouts.services import create_payout, InsufficientBalance
from payouts.models import Payout
from ledger.models import LedgerEntry
from ledger.services import get_balance
from ledger.tests.factories import merchant_with_balance, BankAccountFactory


@pytest.mark.django_db(transaction=True)
def test_concurrent_payouts_dont_overdraw():
    """Two threads each try to withdraw 6000 paise from a 10000 paise balance.
    Exactly one must succeed; the other must be rejected with InsufficientBalance."""
    merchant = merchant_with_balance(10000)
    bank = BankAccountFactory(merchant=merchant)

    barrier = Barrier(2)
    results = {"success": [], "failure": []}

    def attempt():
        barrier.wait()  # both threads released simultaneously
        try:
            payout = create_payout(merchant.id, bank.id, 6000)
            results["success"].append(payout)
        except InsufficientBalance:
            results["failure"].append("InsufficientBalance")
        finally:
            close_old_connections()

    t1 = Thread(target=attempt)
    t2 = Thread(target=attempt)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results["success"]) == 1, f"Expected 1 success, got {len(results['success'])}"
    assert len(results["failure"]) == 1, f"Expected 1 failure, got {len(results['failure'])}"
    assert results["failure"][0] == "InsufficientBalance"
    assert get_balance(merchant.id) == 4000  # 10000 - 6000 hold
    assert Payout.objects.filter(merchant=merchant).count() == 1
    assert LedgerEntry.objects.filter(
        merchant=merchant, reference_type="PAYOUT_HOLD"
    ).count() == 1
