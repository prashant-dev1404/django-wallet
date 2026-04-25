import pytest
from rest_framework.test import APIClient
from ledger.tests.factories import merchant_with_balance as _merchant_with_balance


@pytest.fixture(scope="session", autouse=True)
def assert_postgres():
    from django.db import connection
    assert connection.vendor == "postgresql", (
        "Tests must run against PostgreSQL, not " + connection.vendor
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def merchant_with_balance():
    """Factory fixture: call as merchant_with_balance(amount_paise) -> Merchant."""
    return _merchant_with_balance


@pytest.fixture
def auth_headers():
    """Returns a function: auth_headers(merchant) -> dict for use in client calls."""
    def _make_headers(merchant):
        return {"HTTP_X_MERCHANT_ID": str(merchant.id)}
    return _make_headers
