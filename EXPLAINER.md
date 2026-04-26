# EXPLAINER.md — Playto Pay Payout Engine

Five decisions that determine whether this system is correct under load.

---

## 1. The Ledger

**Balance is never stored. It's recomputed from the ledger every time it's read.**

```python
# backend/ledger/services.py
def get_balance(merchant_id: UUID) -> int:
    result = LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
        balance=Coalesce(
            Sum(Case(
                When(entry_type='CREDIT', then=F('amount_paise')),
                When(entry_type='DEBIT', then=-F('amount_paise')),
                output_field=BigIntegerField(),
            )),
            Value(0),
            output_field=BigIntegerField(),
        )
    )
    return result['balance']
```

Every customer payment, payout hold, and refund is a row in `LedgerEntry`. The table is append-only — `save()` raises if a primary key already exists, so updates are impossible at the model layer.

A stored balance can drift from reality after a partial failure. A derived balance cannot. The database does the math (no Python-side arithmetic between read and write), and money is stored as `BigIntegerField` paise — `1050`, never `10.50` — so floating-point precision and decimal rounding are non-problems by construction.

The cost is an O(n) scan per balance read. At Playto's scale this is irrelevant; if it ever became one, a periodic snapshot row would cap the scan length without changing the model.

---

## 2. The Lock

**Two concurrent payouts cannot overdraw the balance because the second one blocks at the database.**

The naive failure mode: two requests arrive at the same millisecond, both read ₹100, both decide ₹60 is fine, both create a ₹60 hold. Merchant is overdrawn by ₹20. `transaction.atomic()` does not prevent this — at PostgreSQL's default `READ COMMITTED` isolation, two transactions can read the same ledger state simultaneously.

The fix is an explicit row-level lock acquired *before* the balance check:

```python
# backend/ledger/services.py
def get_balance_for_update(merchant_id: UUID) -> int:
    list(
        LedgerEntry.objects.filter(merchant_id=merchant_id)
        .select_for_update()
        .values_list('id', flat=True)
    )
    # ... aggregation as in get_balance ...

# backend/payouts/services.py
def create_payout(merchant_id, bank_account_id, amount_paise):
    with transaction.atomic():
        balance = get_balance_for_update(merchant_id)   # lock held here
        if balance < amount_paise:
            raise InsufficientBalance(balance, amount_paise)
        payout = Payout.objects.create(...)
        create_ledger_entry(..., entry_type="DEBIT", ...)
    # lock released on commit
```

Under concurrency: thread A acquires the lock and proceeds. Thread B blocks at `select_for_update()` until A commits, then sees the new balance (already reduced by A's hold) and correctly raises `InsufficientBalance`.

I chose pessimistic locking over optimistic — no retry loop, simpler to reason about, and throughput isn't the bottleneck for an API where each merchant withdraws a few times a day. Workers use `select_for_update(skip_locked=True)` so multiple worker processes can drain the pending queue in parallel without contending for the same rows.

---

## 3. Idempotency

**A duplicate request never creates a duplicate payout, even if the original is still in flight.**

```python
# backend/idempotency/services.py
def check_or_record(merchant_id, key, request_hash):
    try:
        with transaction.atomic():
            record = IdempotencyKey.objects.create(
                merchant_id=merchant_id,
                key=key,
                request_hash=request_hash,
            )
        return (IdempotencyResult.PROCEED, record)

    except IntegrityError as e:
        if not _is_unique_violation(e):
            raise

    existing = IdempotencyKey.objects.get(merchant_id=merchant_id, key=key)

    if existing.request_hash != request_hash:
        return (IdempotencyResult.CONFLICT, existing)   # 409: key reused with different body
    if existing.response_body is not None:
        return (IdempotencyResult.REPLAY, existing)     # return stored response
    return (IdempotencyResult.IN_FLIGHT, existing)      # 409: original still processing
```

The unique constraint on `(merchant_id, key)` is enforced by the database, so there is no application-level check-then-insert race. A `NULL` `response_body` means "request received, not yet finished" — that's how I distinguish in-flight duplicates from completed ones.

For the in-flight case I return 409 immediately rather than blocking the second request until the first completes. Blocking would tie up a Django worker thread for an unknown duration; 409 is a clear signal that the client should retry shortly. Keys expire 24 hours after creation via a Django-Q scheduled cleanup task.

In-memory or cache-backed idempotency would have been simpler but loses state on deploy or scaling. A payout API that forgets its idempotency keys on restart is unsafe.

---

## 4. The State Machine

**Every status write goes through one gate. Direct assignment doesn't exist anywhere in the codebase.**

```python
# backend/payouts/models.py
ALLOWED_TRANSITIONS = {
    "PENDING":    {"PROCESSING"},
    "PROCESSING": {"COMPLETED", "FAILED", "PENDING"},
    "COMPLETED":  set(),   # terminal
    "FAILED":     set(),   # terminal
}

# backend/payouts/state_machine.py
def transition_to(payout: Payout, new_status: str) -> None:
    allowed = payout.ALLOWED_TRANSITIONS.get(payout.status, set())
    if new_status not in allowed:
        raise IllegalStateTransition(payout.status, new_status)
    payout.status = new_status
    payout.save(update_fields=["status", "updated_at"])
```

`FAILED` and `COMPLETED` map to empty sets, so any transition out of them raises. `FAILED → COMPLETED` specifically is blocked here. The check is centralized — there is exactly one place in the codebase where `payout.status` is written, and every write passes this guard.

Refunds are atomic with the failure transition:

```python
# backend/payouts/services.py
def settle_payout(payout_id, outcome):
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)
        if outcome == "failure":
            transition_to(payout, "FAILED")
            create_ledger_entry(
                merchant=payout.merchant,
                entry_type="CREDIT",
                amount_paise=payout.amount_paise,
                reference_type="PAYOUT_REFUND",
            )
```

Either the status flip and the refund both commit, or neither does. There is no intermediate state where a payout is `FAILED` but the held funds were not returned.

The one backward transition — `PROCESSING → PENDING` — exists because retry is a legitimate operation, gated by `attempt_count < 3` in the worker. I considered hiding it (e.g., resetting `processing_started_at` without a state change) but that would obscure the audit trail. An auditor reading the database should see exactly what happened to every payout, including its retries.

---

## 5. The AI Audit

**One AI-generated bug, caught before it shipped, that would have caused balance corruption under concurrent load.**

I asked the AI to write the payout creation flow. It produced this:

```python
def create_payout(merchant_id, bank_account_id, amount_paise):
    with transaction.atomic():
        balance = get_balance(merchant_id)               # ← no lock
        if balance < amount_paise:
            raise InsufficientBalance(balance, amount_paise)
        payout = Payout.objects.create(...)
        create_ledger_entry(..., entry_type="DEBIT", ...)
```

This looks correct. It's wrapped in a transaction. The balance check precedes the debit. A reviewer skimming the code would likely approve it.

It is wrong. PostgreSQL's default isolation level is `READ COMMITTED`, which permits two transactions to read the same ledger state concurrently. Two simultaneous ₹60 payout requests against a ₹100 balance would both see ₹100, both pass the check, both create a ₹60 hold. The merchant goes to ₹-20. The atomicity of `transaction.atomic()` guarantees nothing about reads — it only ensures the *write* is all-or-nothing.

I caught this by writing the concurrency test first (`Barrier(2)` with two threads each attempting the same withdrawal). The test failed deterministically — two payouts, balance negative.

The fix:

```python
def create_payout(merchant_id, bank_account_id, amount_paise):
    with transaction.atomic():
        balance = get_balance_for_update(merchant_id)    # ← row-level lock
        if balance < amount_paise:
            raise InsufficientBalance(balance, amount_paise)
        payout = Payout.objects.create(...)
        create_ledger_entry(..., entry_type="DEBIT", ...)
```

`get_balance_for_update` adds `select_for_update()` to the query, acquiring a row-level lock that forces the second concurrent transaction to block at the database level until the first commits. The same test now passes ten times in a row.

The lesson I took from this: AI-generated code that *looks* correct on transactional boundaries is the most dangerous category, because the bug is invisible without concurrent load. Every money-touching path in this codebase has a corresponding concurrency test for exactly this reason.