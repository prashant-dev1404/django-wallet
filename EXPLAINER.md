# EXPLAINER.md

> **Status:** to be written *during* implementation, not after. Each answer should be backed by code already in the repo.

The challenge says this is where most candidates get filtered out. Treat it as the primary deliverable. Five questions, each answered in:

- **2–4 sentences of explanation**
- **A code snippet pasted from the actual repo** (with file path)
- **One sentence on the trade-off or alternative considered**

Keep answers tight. The reviewer reads dozens of these. Density and precision win over verbosity.

---

## 1. The Ledger

**Question:** Paste your balance calculation query. Why did you model credits and debits this way?

**To write:**
- Paste the `Sum(Case(When(...)))` aggregation from `backend/ledger/services.py::get_balance`.
- Why append-only: auditability, no drift, database is source of truth.
- Why credits/debits as separate types instead of signed amounts: explicit semantics, easier to filter for reports, matches double-entry accounting conventions.
- Trade-off: reads are O(n) in ledger entries per merchant. Acceptable at this scale; would add periodic snapshots if it grew.

---

## 2. The Lock

**Question:** Paste the exact code that prevents two concurrent payouts from overdrawing a balance. Explain what database primitive it relies on.

**To write:**
- Paste the `select_for_update()` block from `backend/payouts/services.py::create_payout`.
- The primitive: PostgreSQL row-level lock via `SELECT ... FOR UPDATE`. Acquired inside `transaction.atomic()`. Second concurrent request blocks at the SELECT until first commits.
- Why not optimistic locking: simpler, no retry logic, throughput is not the constraint at our scale.
- Why not a CHECK constraint on a balance column: there is no balance column.

---

## 3. The Idempotency

**Question:** How does your system know it has seen a key before? What happens if the first request is in flight when the second arrives?

**To write:**
- Database table `idempotency_idempotencykey` with `UNIQUE(merchant_id, key)`.
- Insert attempted before any business logic. Unique violation = duplicate.
- If duplicate found and `response_body` is populated: return stored response.
- If duplicate found and `response_body` is null: original is in flight, return 409 with retry hint.
- Trade-off: chose 409 over blocking-wait to avoid tying up worker threads on slow originals.
- Mention 24h expiration via scheduled cleanup task.

---

## 4. The State Machine

**Question:** Where in the code is failed-to-completed blocked? Show the check.

**To write:**
- Paste `ALLOWED_TRANSITIONS` dict from `backend/payouts/state_machine.py`.
- Paste `transition_to()` method showing the `if new_status not in ALLOWED_TRANSITIONS[self.status]: raise IllegalStateTransition`.
- Note that `FAILED` maps to an empty set, so `failed → completed` raises.
- Note `COMPLETED` and `FAILED` are terminal (empty allowed sets).
- Mention the one backward transition (`PROCESSING → PENDING`) is gated on `attempt_count < 3` in the worker, not in the state machine itself — and explain why this is honest rather than a strict-forward-only fiction.

---

## 5. The AI Audit

**Question:** One specific example where AI wrote subtly wrong code. Paste what it gave you, what you caught, and what you replaced it with.

**To write during development:** keep a scratch file `ai-audit-notes.md` (gitignored) where you paste any AI suggestion that was subtly wrong. The best ones to surface in the EXPLAINER:

**Candidate 1 — Python-side balance arithmetic:**
> AI suggested: `merchant.balance = merchant.balance - amount; merchant.save()`
> Caught because: there is no `balance` field. But the deeper bug is the read-modify-write pattern is racy even *with* a balance field — two concurrent transactions both read the same balance, both subtract, both save, one update is lost.
> Replaced with: aggregation query inside `select_for_update()` block.

**Candidate 2 — Forgotten lock:**
> AI suggested wrapping the payout creation in `transaction.atomic()` only.
> Caught because: `atomic()` provides a transaction boundary but no row-level lock. Postgres default isolation (READ COMMITTED) lets two transactions both read the same balance simultaneously.
> Replaced with: explicit `.select_for_update()` on the merchant's ledger rows.

**Candidate 3 — Bank call inside transaction:**
> AI suggested putting the simulated `time.sleep` (representing bank settlement) inside the same `transaction.atomic()` block as the state transition.
> Caught because: would hold the row lock for the duration of the external call. Under load, this serializes all payouts for a merchant behind one slow bank call.
> Replaced with: state transition commits first, settlement call happens outside, second transaction records outcome.

**Candidate 4 — Aggregating with default value bug:**
> AI suggested `LedgerEntry.objects.filter(...).aggregate(Sum('amount_paise'))['amount_paise__sum']` without handling the empty case.
> Caught because: returns `None` for a merchant with no entries, and `None - 1000` blows up.
> Replaced with: `... or 0` coalesce, or use `Coalesce(Sum(...), Value(0))`.

Pick whichever one actually happens during your build. Don't fabricate.
