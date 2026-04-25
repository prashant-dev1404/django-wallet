# payouts/admin.py
#
# Read-only admin for Payout. Useful during development to inspect what
# happened. Disable add/change/delete in the admin — payouts only move
# through the state machine, never via direct edits.
#
# class PayoutAdmin(admin.ModelAdmin):
#     list_display = ["id", "merchant", "amount_paise", "status",
#                     "attempt_count", "created_at"]
#     list_filter = ["status"]
#     search_fields = ["id", "merchant__email"]
#     readonly_fields = [<all fields>]
#     def has_add_permission(self, request): return False
#     def has_change_permission(self, request, obj=None): return False
#     def has_delete_permission(self, request, obj=None): return False
