# payouts/state_machine.py
#
# Centralized state transition logic. EVERY status write goes through here.
# This is the file referenced in EXPLAINER.md question 4.
#
# ============================================================================
# IllegalStateTransition exception
# ============================================================================
# class IllegalStateTransition(Exception):
#     def __init__(self, current: str, requested: str):
#         self.current = current
#         self.requested = requested
#         super().__init__(
#             f"Cannot transition from {current} to {requested}"
#         )
#
# ============================================================================
# transition_to(payout: Payout, new_status: str) -> None
# ============================================================================
# Pseudocode:
#
#   def transition_to(payout, new_status: str) -> None:
#       allowed = payout.ALLOWED_TRANSITIONS.get(payout.status, set())
#       if new_status not in allowed:
#           raise IllegalStateTransition(payout.status, new_status)
#       payout.status = new_status
#       payout.save(update_fields=["status", "updated_at"])
#
# IMPORTANT POINTS:
#
# 1. The check uses `not in allowed`. If `payout.status` is somehow not in
#    ALLOWED_TRANSITIONS at all (data corruption), `.get(..., set())` returns
#    an empty set, so any transition is rejected. Fail closed.
#
# 2. `update_fields` is explicit. Without it, save() writes every field, which
#    can race with other transactions modifying other fields. Be surgical.
#
# 3. This function does NOT manage the transaction. The CALLER must wrap
#    transition_to() and any related side effects (e.g. creating a refund
#    ledger entry) inside a single transaction.atomic() block.
#
# 4. Do NOT add side effects here (no signals, no ledger writes). Side effects
#    live with the caller, who has the full context and the transaction.
#    Example: the worker calls transition_to(FAILED) AND creates the refund
#    entry, both inside one atomic block. State machine doesn't know about
#    refunds; it just enforces the transition.
#
# 5. Why `PROCESSING -> PENDING` is allowed:
#    The retry path needs it. We acknowledge this is the one backward
#    transition and defend it in the EXPLAINER:
#      "Retry is a legitimate concept; pretending we have strict-forward-only
#       transitions while sneaking the retry through some other mechanism
#       would be dishonest. We allow it explicitly and gate it on
#       attempt_count < 3 in the worker."
#
# ============================================================================
# can_transition(payout: Payout, new_status: str) -> bool
# ============================================================================
# Convenience predicate for views/serializers that want to check without
# raising. Just returns the boolean.
