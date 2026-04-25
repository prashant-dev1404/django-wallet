# idempotency app — owns the IdempotencyKey model and the check-or-record
# service that the payout view uses to dedupe requests.
#
# Lives as a separate app (rather than inside payouts) because if Playto Pay
# adds more endpoints later (refunds, chargebacks), they'll all need the same
# idempotency mechanism.
