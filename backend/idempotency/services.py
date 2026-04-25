from uuid import UUID
from typing import Tuple, Optional, Union
from django.db import transaction, IntegrityError
from django.utils import timezone
from datetime import timedelta
from .models import IdempotencyKey


class IdempotencyResult:
    """Result types for idempotency check operations."""
    PROCEED = "PROCEED"      # New key, caller should run business logic
    REPLAY = "REPLAY"        # Duplicate with stored response, return it as-is
    IN_FLIGHT = "IN_FLIGHT"  # Duplicate, original still processing
    CONFLICT = "CONFLICT"    # Duplicate key, but request body differs from original


def _is_unique_violation(error: IntegrityError) -> bool:
    """Check if the IntegrityError is a unique constraint violation."""
    # PostgreSQL unique violation error code
    return 'unique constraint' in str(error).lower() or '23505' in str(error)


def check_or_record(
    merchant_id: UUID,
    key: str,
    request_hash: str
) -> Tuple[str, Optional[IdempotencyKey]]:
    """
    Check for existing idempotency key or record a new one.

    Args:
        merchant_id: UUID of the merchant
        key: Idempotency key string
        request_hash: Hash of the request body

    Returns:
        Tuple of (result_type, existing_record_or_none)
    """
    try:
        with transaction.atomic():
            record = IdempotencyKey.objects.create(
                merchant_id=merchant_id,
                key=key,
                request_hash=request_hash,
            )
        return (IdempotencyResult.PROCEED, record)

    except IntegrityError as e:
        # Check if it's a unique constraint violation
        if not _is_unique_violation(e):
            raise

    # We hit the unique constraint. Fetch the existing row.
    try:
        existing = IdempotencyKey.objects.get(
            merchant_id=merchant_id,
            key=key
        )
    except IdempotencyKey.DoesNotExist:
        # This shouldn't happen if we got a unique violation, but handle it
        raise

    # Check if the request hash matches
    if existing.request_hash != request_hash:
        return (IdempotencyResult.CONFLICT, existing)

    # Check if we have a stored response (completed request)
    if existing.response_body is not None:
        return (IdempotencyResult.REPLAY, existing)

    # Request is still in flight
    return (IdempotencyResult.IN_FLIGHT, existing)


def record_response(idempotency_key: IdempotencyKey, response_body: str, status_code: int) -> None:
    """
    Record the response for a completed idempotent request.

    Args:
        idempotency_key: The IdempotencyKey instance
        response_body: JSON response body as string
        status_code: HTTP status code
    """
    idempotency_key.response_body = response_body
    idempotency_key.response_status = status_code
    idempotency_key.completed_at = timezone.now()
    idempotency_key.save()


def cleanup_expired_keys() -> int:
    """
    Clean up idempotency keys older than 24 hours.

    Returns:
        Number of keys deleted
    """
    cutoff = timezone.now() - timedelta(hours=24)
    deleted_count, _ = IdempotencyKey.objects.filter(
        created_at__lt=cutoff
    ).delete()
    return deleted_count
#
#       return ("REPLAY", existing)
#
# ============================================================================
# record_response(record: IdempotencyKey, status: int, body: dict,
#                 payout_id: UUID | None = None) -> None
# ============================================================================
# Called by the view after the business logic succeeds (or fails with a
# response-worthy error).
#
#   def record_response(record, status, body, payout_id=None):
#       record.response_status = status
#       record.response_body = body
#       record.payout_id = payout_id
#       record.save(update_fields=["response_status", "response_body",
#                                  "payout_id"])
#
# CRITICAL: The view must call record_response() in a finally-style guarantee
# for any final response (success OR client error like 402/422). Otherwise
# the row stays NULL and future duplicates appear in-flight forever — until
# the 24h cleanup wipes them.
#
# A 5xx error (server crash) intentionally does NOT record a response. The
# client retrying with the same key is then handled by the next attempt.
# This is the correct trade-off: retry-on-server-error is desirable.
#
# ============================================================================
# expire_old_keys() -> int
# ============================================================================
# Called hourly by the worker. Returns the count of deleted rows.
#
#   def expire_old_keys() -> int:
#       cutoff = timezone.now() - timedelta(hours=24)
#       deleted, _ = IdempotencyKey.objects.filter(
#           created_at__lt=cutoff
#       ).delete()
#       return deleted
#
# ============================================================================
# Helper: canonical request hashing
# ============================================================================
# def hash_request_body(body: dict) -> str:
#     # json.dumps with sort_keys=True for stable ordering, then SHA256.
#     # Used by the view before calling check_or_record.
#     canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
#     return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
