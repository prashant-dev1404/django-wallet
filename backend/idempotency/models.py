from django.db import models


class IdempotencyKey(models.Model):
    id = models.BigAutoField(primary_key=True)
    merchant = models.ForeignKey(
        'ledger.Merchant',
        on_delete=models.CASCADE
    )
    key = models.CharField(max_length=64)  # client-supplied UUID as string
    request_hash = models.CharField(max_length=64)  # SHA256 hex of canonical request body
    response_status = models.IntegerField(null=True, blank=True)  # filled after handling
    response_body = models.JSONField(null=True, blank=True)  # filled after handling
    payout = models.ForeignKey(
        'payouts.Payout',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )  # Optional link back to the resource created by this request, for debugging
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = [("merchant", "key")]
        indexes = [
            models.Index(fields=['merchant', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"IdempotencyKey {self.key} for {self.merchant.name}"
