from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from ledger.models import Merchant, BankAccount, LedgerEntry
from ledger.services import get_balance


MERCHANTS = [
    {
        "name": "Acme Design Studio",
        "email": "acme@test.local",
        "bank_accounts": [
            {"account_number_masked": "XXXX1234", "ifsc": "HDFC0001234", "account_holder_name": "Acme Design Studio"},
            {"account_number_masked": "XXXX5678", "ifsc": "ICIC0002345", "account_holder_name": "Acme Design Studio"},
        ],
        # (amount_paise, days_ago) — sums to 50,000,000 paise (₹5,00,000)
        "credits": [
            (10000000, 30), (10000000, 25), (10000000, 20),
            (10000000, 15), (5000000, 10), (5000000, 5),
        ],
    },
    {
        "name": "Bharat Freelancers Co",
        "email": "bharat@test.local",
        "bank_accounts": [
            {"account_number_masked": "XXXX9012", "ifsc": "SBIN0003456", "account_holder_name": "Bharat Freelancers"},
            {"account_number_masked": "XXXX3456", "ifsc": "AXIS0004567", "account_holder_name": "Bharat Freelancers"},
        ],
        # sums to 12,500,000 paise (₹1,25,000)
        "credits": [
            (3000000, 28), (3000000, 22), (2500000, 18),
            (2000000, 12), (2000000, 7),
        ],
    },
    {
        "name": "Mango Tech LLP",
        "email": "mango@test.local",
        "bank_accounts": [
            {"account_number_masked": "XXXX7890", "ifsc": "KKBK0005678", "account_holder_name": "Mango Tech LLP"},
            {"account_number_masked": "XXXX2345", "ifsc": "PNB0006789", "account_holder_name": "Mango Tech LLP"},
        ],
        # sums to 200,000 paise (₹2,000)
        "credits": [
            (50000, 27), (50000, 20), (50000, 13), (50000, 6),
        ],
    },
]


class Command(BaseCommand):
    help = "Seed test merchants, bank accounts, and credits. Idempotent."

    def handle(self, *args, **options):
        with transaction.atomic():
            for data in MERCHANTS:
                merchant, created = Merchant.objects.get_or_create(
                    email=data["email"],
                    defaults={"name": data["name"]},
                )
                status = "Created" if created else "Exists"
                self.stdout.write(f"{status}: {merchant.name}")

                for ba_data in data["bank_accounts"]:
                    BankAccount.objects.get_or_create(
                        merchant=merchant,
                        account_number_masked=ba_data["account_number_masked"],
                        defaults={
                            "ifsc": ba_data["ifsc"],
                            "account_holder_name": ba_data["account_holder_name"],
                        },
                    )

                if created:
                    for amount_paise, days_ago in data["credits"]:
                        entry = LedgerEntry.objects.create(
                            merchant=merchant,
                            entry_type="CREDIT",
                            amount_paise=amount_paise,
                            reference_type="CUSTOMER_PAYMENT",
                            description="Seeded credit",
                        )
                        # auto_now_add forces current time; backdate via queryset update
                        LedgerEntry.objects.filter(id=entry.id).update(
                            created_at=timezone.now() - timedelta(days=days_ago)
                        )

        self.stdout.write("\n=== Seeded Merchants ===")
        for merchant in Merchant.objects.all():
            balance = get_balance(merchant.id)
            self.stdout.write(
                f"\n{merchant.name}\n"
                f"  Merchant UUID : {merchant.id}\n"
                f"  Balance       : {balance} paise (₹{balance / 100:,.2f})"
            )
            for ba in merchant.bank_accounts.all():
                self.stdout.write(f"  Bank Account  : {ba.account_number_masked}  UUID: {ba.id}")
