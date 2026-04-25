import uuid
from django.db import models


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.email})"


class BankAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.PROTECT,
        related_name="bank_accounts"
    )
    account_number_masked = models.CharField(max_length=20)  # e.g. "XXXX1234"
    ifsc = models.CharField(max_length=11)
    account_holder_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.account_holder_name} - {self.account_number_masked}"


class LedgerEntry(models.Model):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    ENTRY_TYPE_CHOICES = [
        (CREDIT, "Credit"),
        (DEBIT, "Debit"),
    ]

    id = models.BigAutoField(primary_key=True)
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.PROTECT,
        related_name="ledger_entries"
    )
    entry_type = models.CharField(
        max_length=10,
        choices=ENTRY_TYPE_CHOICES
    )
    amount_paise = models.BigIntegerField()  # always positive, sign comes from entry_type
    reference_type = models.CharField(max_length=50)
    reference_id = models.UUIDField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_paise__gt=0),
                name="ledgerentry_amount_positive"
            ),
        ]
        indexes = [
            models.Index(fields=['merchant', 'created_at']),
            models.Index(fields=['merchant', 'reference_type', 'reference_id']),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("LedgerEntry is append-only — updates are forbidden")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.entry_type} {self.amount_paise} paise for {self.merchant.name} - {self.reference_type}"
