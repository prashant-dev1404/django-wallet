import uuid
from django.db import models
from django.core.exceptions import ValidationError


class Payout(models.Model):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (PROCESSING, "Processing"),
        (COMPLETED, "Completed"),
        (FAILED, "Failed"),
    ]

    ALLOWED_TRANSITIONS = {
        PENDING: {PROCESSING},
        PROCESSING: {COMPLETED, FAILED, PENDING},  # PENDING = retry
        COMPLETED: set(),  # terminal
        FAILED: set(),  # terminal
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        'ledger.Merchant',
        on_delete=models.PROTECT,
        related_name="payouts"
    )
    bank_account = models.ForeignKey(
        'ledger.BankAccount',
        on_delete=models.PROTECT
    )
    amount_paise = models.BigIntegerField()  # always positive
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
        db_index=True
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    failure_reason = models.TextField(blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_paise__gt=0),
                name="payout_amount_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "PROCESSING", "COMPLETED", "FAILED"]),
                name="payout_status_valid"
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['merchant', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Payout {self.id} - {self.amount_paise} paise to {self.merchant.name}"

    def clean(self):
        if self.amount_paise <= 0:
            raise ValidationError("Amount must be positive")

    def transition_to(self, new_status):
        """Transition to a new status, validating the transition is allowed."""
        from .state_machine import transition_to
        transition_to(self, new_status)
#   payout enters PROCESSING, so the stuck-detection query is unambiguous.
