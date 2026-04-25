# payouts/exceptions.py
#
# Domain-specific exceptions. Caught at the view layer.
#
# class IllegalStateTransition(Exception):
#     # Defined in state_machine.py for proximity to the rule it enforces.
#     # Re-export here for callers that want to catch it without importing
#     # the state machine.
#
# class BankAccountNotFound(Exception):
#     """Bank account ID doesn't exist or doesn't belong to this merchant."""
#
# # InsufficientBalance and InvalidAmount live in ledger/exceptions.py.
# # Import them here for view-layer try/except blocks if useful.
