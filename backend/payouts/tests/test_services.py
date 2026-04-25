# payouts/tests/test_services.py
#
# Tests for create_payout, settle_payout, retry_or_fail.
# Plain `db` fixture is fine for all of these — concurrency tests live in
# their own file.
#
# create_payout:
# 1. test_create_payout_with_sufficient_balance
#    - Assert payout created in PENDING, hold ledger entry created,
#      balance reduced.
# 2. test_create_payout_insufficient_balance_raises
#    - Assert InsufficientBalance raised, no payout, no ledger entry.
# 3. test_create_payout_invalid_amount_raises
#    - amount_paise <= 0
# 4. test_create_payout_with_other_merchants_bank_account_raises
#    - Bank account belongs to different merchant -> BankAccountNotFound.
# 5. test_create_payout_atomicity
#    - Force a failure between Payout.create and ledger.debit (mock).
#    - Assert nothing is committed (no orphaned payout).
#
# settle_payout:
# 6. test_settle_success_keeps_hold_as_final_debit
#    - status -> COMPLETED, no new ledger entries, balance unchanged.
# 7. test_settle_failure_creates_refund_credit
#    - status -> FAILED, CREDIT entry created with reference_type=PAYOUT_REFUND,
#      balance restored to pre-payout state.
# 8. test_settle_failure_atomicity
#    - Mock ledger.credit to raise; assert status was NOT updated either.
#
# retry_or_fail:
# 9. test_retry_increments_attempt_and_returns_to_pending
# 10. test_retry_third_failure_marks_failed_and_refunds
# 11. test_retry_sets_backoff_correctly
#     - attempt_count=1 -> processing_started_at ~ now+5s
#     - attempt_count=2 -> ~ now+10s
#     - attempt_count=3 -> ~ now+20s (allow tolerance)
