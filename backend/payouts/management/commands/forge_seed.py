"""
Deterministic fixture seeder for test-forge generated tests.

Unlike the regular `seed` command (which creates merchants with random UUIDs
on each run), this command creates a single fixture merchant + bank account
with FIXED, well-known UUIDs that test-forge's generated test files can
reference directly. Idempotent: running it twice is safe.

Generated tests should send the X-Merchant-Id header set to FORGE_MERCHANT_UUID
(see backend/.env.test-forge.example for the canonical value).

Usage:
    python manage.py forge_seed
    python manage.py forge_seed --balance 10000000   # 1,00,000 paise = 1L INR
"""

from uuid import UUID
from django.core.management.base import BaseCommand
from django.db import transaction
from ledger.models import Merchant, BankAccount, LedgerEntry


# Fixed UUIDs — DO NOT CHANGE without updating .env.test-forge.example and
# any committed generated tests that hardcode them.
FORGE_MERCHANT_UUID = UUID("00000000-0000-0000-0000-000000000001")
FORGE_BANK_ACCOUNT_UUID = UUID("00000000-0000-0000-0000-000000000010")

DEFAULT_BALANCE_PAISE = 50_000_000  # ₹5,00,000


class Command(BaseCommand):
    help = (
        "Create deterministic test fixtures for test-forge: a merchant with a "
        "well-known UUID, one bank account, and a credit so the balance is "
        "non-zero. Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--balance",
            type=int,
            default=DEFAULT_BALANCE_PAISE,
            help=f"Starting balance in paise (default: {DEFAULT_BALANCE_PAISE:,}).",
        )

    def handle(self, *args, **options):
        balance_paise = options["balance"]

        with transaction.atomic():
            merchant, created = Merchant.objects.get_or_create(
                id=FORGE_MERCHANT_UUID,
                defaults={
                    "name": "Forge Test Merchant",
                    "email": "forge-test@test-forge.local",
                },
            )
            self.stdout.write(
                f"{'Created' if created else 'Exists'}: merchant {merchant.id} ({merchant.name})"
            )

            bank_account, ba_created = BankAccount.objects.get_or_create(
                id=FORGE_BANK_ACCOUNT_UUID,
                defaults={
                    "merchant": merchant,
                    "account_number_masked": "XXXX0001",
                    "ifsc": "HDFC0000001",
                    "account_holder_name": "Forge Test Merchant",
                },
            )
            self.stdout.write(
                f"{'Created' if ba_created else 'Exists'}: bank account {bank_account.id}"
            )

            # Only seed balance once — re-running shouldn't double-credit.
            if created:
                LedgerEntry.objects.create(
                    merchant=merchant,
                    entry_type="CREDIT",
                    amount_paise=balance_paise,
                    reference_type="CUSTOMER_PAYMENT",
                )
                self.stdout.write(
                    f"Credited: {balance_paise:,} paise opening balance"
                )
            else:
                self.stdout.write("Skipping credit (merchant already existed)")

        self.stdout.write(self.style.SUCCESS("forge_seed complete."))
