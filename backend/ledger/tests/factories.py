import factory
from ledger.models import Merchant, BankAccount, LedgerEntry


class MerchantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Merchant

    name = factory.Sequence(lambda n: f"Test Merchant {n}")
    email = factory.Sequence(lambda n: f"merchant{n}@test.local")


class BankAccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BankAccount

    merchant = factory.SubFactory(MerchantFactory)
    account_number_masked = "XXXX1234"
    ifsc = "HDFC0001234"
    account_holder_name = "Test Holder"


class LedgerEntryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LedgerEntry

    merchant = factory.SubFactory(MerchantFactory)
    entry_type = "CREDIT"
    amount_paise = 10000
    reference_type = "TEST"
    description = "Test entry"


def merchant_with_balance(amount_paise: int) -> Merchant:
    """Create a merchant with a single seeded credit. Used by concurrency tests."""
    m = MerchantFactory()
    LedgerEntryFactory(
        merchant=m,
        entry_type="CREDIT",
        amount_paise=amount_paise,
        reference_type="SEED",
    )
    return m
