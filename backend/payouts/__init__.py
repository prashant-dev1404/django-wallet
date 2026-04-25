# payouts app — owns Payout, the state machine, the API endpoints, and the
# background workers that move payouts through their lifecycle.
#
# This app depends on `ledger` for balance and entry creation. It does NOT
# depend on `idempotency` directly — idempotency is wired in at the view layer.
