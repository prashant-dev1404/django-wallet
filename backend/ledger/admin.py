# ledger/admin.py
#
# Optional but useful for local debugging.
#
# Register Merchant and BankAccount with basic ModelAdmin.
# For LedgerEntry: register READ-ONLY (has_add_permission=False,
#                                      has_change_permission=False,
#                                      has_delete_permission=False).
# Append-only enforcement extends to the admin.
