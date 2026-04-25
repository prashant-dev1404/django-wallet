import pytest
import uuid
from rest_framework.test import APIClient
from payouts.models import Payout
from ledger.models import LedgerEntry
from idempotency.models import IdempotencyKey
from ledger.tests.factories import merchant_with_balance, BankAccountFactory

PAYOUTS_URL = "/api/v1/payouts"


@pytest.mark.django_db
def test_duplicate_key_returns_same_response():
    merchant = merchant_with_balance(100000)
    bank = BankAccountFactory(merchant=merchant)
    key = str(uuid.uuid4())
    body = {"amount_paise": 5000, "bank_account_id": str(bank.id)}
    headers = {
        "HTTP_IDEMPOTENCY_KEY": key,
        "HTTP_X_MERCHANT_ID": str(merchant.id),
    }

    client = APIClient()
    r1 = client.post(PAYOUTS_URL, body, format="json", **headers)
    r2 = client.post(PAYOUTS_URL, body, format="json", **headers)

    assert r1.status_code == 201
    assert r2.status_code == 201  # returns original stored status
    assert r1.json()["id"] == r2.json()["id"]
    assert Payout.objects.count() == 1
    assert LedgerEntry.objects.filter(reference_type="PAYOUT_HOLD").count() == 1


@pytest.mark.django_db
def test_duplicate_key_with_different_body_returns_409():
    merchant = merchant_with_balance(100000)
    bank = BankAccountFactory(merchant=merchant)
    key = str(uuid.uuid4())
    headers = {
        "HTTP_IDEMPOTENCY_KEY": key,
        "HTTP_X_MERCHANT_ID": str(merchant.id),
    }

    client = APIClient()
    r1 = client.post(
        PAYOUTS_URL,
        {"amount_paise": 5000, "bank_account_id": str(bank.id)},
        format="json",
        **headers,
    )
    r2 = client.post(
        PAYOUTS_URL,
        {"amount_paise": 9999, "bank_account_id": str(bank.id)},
        format="json",
        **headers,
    )

    assert r1.status_code == 201
    assert r2.status_code == 409
    assert Payout.objects.count() == 1


@pytest.mark.django_db
def test_missing_idempotency_key_returns_400():
    merchant = merchant_with_balance(100000)
    bank = BankAccountFactory(merchant=merchant)
    client = APIClient()
    r = client.post(
        PAYOUTS_URL,
        {"amount_paise": 5000, "bank_account_id": str(bank.id)},
        format="json",
        HTTP_X_MERCHANT_ID=str(merchant.id),
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_invalid_idempotency_key_format_returns_400():
    merchant = merchant_with_balance(100000)
    bank = BankAccountFactory(merchant=merchant)
    client = APIClient()
    r = client.post(
        PAYOUTS_URL,
        {"amount_paise": 5000, "bank_account_id": str(bank.id)},
        format="json",
        HTTP_X_MERCHANT_ID=str(merchant.id),
        HTTP_IDEMPOTENCY_KEY="not-a-uuid!!!",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_in_flight_duplicate_returns_409():
    """Simulates in-flight by pre-creating an IdempotencyKey with no response."""
    merchant = merchant_with_balance(100000)
    bank = BankAccountFactory(merchant=merchant)
    key = str(uuid.uuid4())

    # Manually create a key with no recorded response (simulating in-flight)
    IdempotencyKey.objects.create(
        merchant=merchant,
        key=key,
        request_hash="abc123",
    )

    client = APIClient()
    r = client.post(
        PAYOUTS_URL,
        {"amount_paise": 5000, "bank_account_id": str(bank.id)},
        format="json",
        HTTP_X_MERCHANT_ID=str(merchant.id),
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert r.status_code == 409


@pytest.mark.django_db
def test_keys_scoped_per_merchant():
    """Two merchants sharing the same UUID key both get independent payouts."""
    merchant_a = merchant_with_balance(100000)
    merchant_b = merchant_with_balance(100000)
    bank_a = BankAccountFactory(merchant=merchant_a)
    bank_b = BankAccountFactory(merchant=merchant_b)
    shared_key = str(uuid.uuid4())

    client = APIClient()
    ra = client.post(
        PAYOUTS_URL,
        {"amount_paise": 5000, "bank_account_id": str(bank_a.id)},
        format="json",
        HTTP_X_MERCHANT_ID=str(merchant_a.id),
        HTTP_IDEMPOTENCY_KEY=shared_key,
    )
    rb = client.post(
        PAYOUTS_URL,
        {"amount_paise": 5000, "bank_account_id": str(bank_b.id)},
        format="json",
        HTTP_X_MERCHANT_ID=str(merchant_b.id),
        HTTP_IDEMPOTENCY_KEY=shared_key,
    )

    assert ra.status_code == 201
    assert rb.status_code == 201
    assert ra.json()["id"] != rb.json()["id"]
    assert Payout.objects.count() == 2
