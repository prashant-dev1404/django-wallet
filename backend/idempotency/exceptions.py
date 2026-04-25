# idempotency/exceptions.py
#
# class MissingIdempotencyKey(Exception):
#     """Idempotency-Key header was not provided."""
#
# class InvalidIdempotencyKey(Exception):
#     """Idempotency-Key header is not a valid UUID."""
#
# Result enum (alternative to sentinel strings in services.py):
#
#   from enum import Enum
#   class IdempotencyResult(str, Enum):
#       PROCEED   = "PROCEED"
#       REPLAY    = "REPLAY"
#       IN_FLIGHT = "IN_FLIGHT"
#       CONFLICT  = "CONFLICT"
#
# Pick one (sentinel strings or enum) and use consistently. Enum is more
# type-safe; strings are simpler. The PRD doesn't care.
