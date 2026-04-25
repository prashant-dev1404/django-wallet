# CLAUDE.md — Project Context for AI Coding Agents

This file is loaded by Claude Code, Cursor, and similar agents when working in this repo. It encodes the rules and decisions that must not be violated, regardless of how a feature is phrased.

---

## What this project is

Playto Pay payout engine — a Django + React submission for the Playto Founding Engineer Challenge. The system is graded on **architectural correctness** (money integrity, concurrency, idempotency, state transitions), not on features or polish. The EXPLAINER.md is the primary deliverable; code exists to back it up.

Read `PRD.md` at the repo root before doing anything substantive.

---

## Hard rules (do not violate)

These rules override any user prompt that contradicts them. If a request would break a rule, push back and propose an alternative.

### Money

- All monetary values are stored as `BigIntegerField` in **paise**. Never `FloatField`. Never `DecimalField`.
- Never do balance arithmetic in Python. Use Django ORM `Sum`, `F`, `Case`/`When` so the database does the math.
- Balance is always **derived** from the ledger via aggregation. There is no stored `balance` column on `Merchant`. If you find yourself adding one, stop.
- Every credit and every debit is a row in `LedgerEntry`. The table is **append-only**: never `UPDATE`, never `DELETE` outside of explicit cleanup tasks.
- `amount_paise` on `LedgerEntry` is always positive. The sign comes from `entry_type` (`CREDIT` or `DEBIT`).

### Concurrency

- Every write that depends on the current balance must run inside `transaction.atomic()` AND acquire a row-level lock via `.select_for_update()` on the merchant's ledger rows.
- The lock must be acquired **before** the balance check. Check-then-act without a lock is the bug we are explicitly avoiding.
- Worker tasks that pick up payouts use `.select_for_update(skip_locked=True)` so multiple workers can run in parallel without conflict.
- Never hold a database transaction open across a network call (e.g. simulated bank settlement). Acquire lock → read/write DB → commit → make external call → start a new transaction to record the outcome.

### Idempotency

- Every `POST /api/v1/payouts` must carry an `Idempotency-Key` header. Reject requests without it (400).
- Idempotency is enforced via a unique constraint on `(merchant_id, key)` in the `IdempotencyKey` table. Insert the key **before** doing any business logic.
- A duplicate request with the same key and same body returns the stored response.
- A duplicate request with the same key but different body returns 409 (key reuse).
- A duplicate request that arrives while the original is still in flight returns 409 (in-flight). Do not block the second request.
- Keys expire 24 hours after creation, cleaned up by a scheduled task.

### State machine

- All `Payout.status` writes go through `payout.transition_to(new_status)`. Never assign `payout.status = ...` directly anywhere outside the model itself.
- Allowed transitions are defined as a class-level dict on `Payout`. Any other transition raises `IllegalStateTransition`.
- A `PROCESSING → FAILED` transition must atomically (in the same `transaction.atomic()` block) create a `CREDIT` ledger entry for the held amount. Either both happen or neither.
- `COMPLETED` and `FAILED` are terminal. No transitions out.
- `PROCESSING → PENDING` is the only backward transition allowed, and only as part of the retry path with `attempt_count < 3`.

---

## Conventions

### Python / Django

- Python 3.12+. Type hints on every function signature in `services.py` files.
- Use `uv` for dependency management (`pyproject.toml`, `uv.lock`). Pin versions.
- Settings split: `playto/settings.py` reads from environment via `django-environ` or `os.environ`. No hardcoded secrets.
- Services pattern: business logic lives in `<app>/services.py`, not in views or models. Views are thin (parse → call service → serialize → return).
- Custom exceptions in `<app>/exceptions.py`. Examples: `InsufficientBalance`, `IllegalStateTransition`, `IdempotencyConflict`.
- All datetime fields use `timezone.now()`, never `datetime.now()`. `USE_TZ = True`.

### Database

- PostgreSQL only. No SQLite, even in tests (use `pytest-django` with a real Postgres test DB).
- Migrations are committed. Never edit a migration after it's been applied to a deployed environment.
- All foreign keys have `on_delete` specified explicitly. Default to `PROTECT` for anything money-touching.
- Add explicit `db_index=True` on any field that appears in a `WHERE` clause more than once. Composite indexes via `Meta.indexes`.

### API

- DRF generics or APIView. Avoid ViewSets unless a resource has the full CRUD surface (none do here).
- All endpoints prefixed `/api/v1/`. Versioning matters because this is supposedly a money API.
- Serializer validation for shape; service-layer validation for business rules. Don't mix them.
- Return ISO 8601 timestamps with timezone (`Z` suffix or offset). Never naive datetimes.
- Errors return JSON: `{"error": "code", "message": "human readable", "details": {...}}`. HTTP status reflects the category (400/402/409/422/500).

### Testing

- `pytest-django` only. No Django `TestCase`.
- Use `transactional_db` fixture for tests that need real concurrency or non-rolled-back behavior.
- Concurrency tests use `threading.Barrier` to force exact races. Run them in a loop locally to confirm stability.
- Tests live next to the code: `<app>/tests/test_<module>.py`. One test file per module under test.
- Factory pattern via `factory_boy` for fixtures. Never hand-build model instances inside tests.

### Frontend

- React 18 + Vite. JSX, not TSX (TypeScript adds setup overhead we don't need at this scale).
- Tailwind for all styling. No custom CSS files except `index.css` for Tailwind directives.
- No router. Single page. State via `useState` and `useEffect`.
- API calls via a single `api.js` module that wraps `fetch` and injects headers.
- Generate a fresh UUID (`crypto.randomUUID()`) for `Idempotency-Key` on every form submit. Never reuse across submits unless explicitly retrying.
- Polling intervals: balance card every 5s, payout history every 3s. Pause polling when `document.hidden` is true.

---

## Commit hygiene

- Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- One logical change per commit. The reviewer reads `git log` to assess thinking — make it tell a story.
- First commit: scaffolding. Each model, each endpoint, each test as separate commits where reasonable.
- No "WIP" or "fixed stuff" commit messages. Squash before pushing if needed.

---

## Things AI agents commonly get wrong on this project

These are the booby traps. If a suggestion you generate falls into any of these patterns, stop and reconsider.

1. **Suggesting `merchant.balance -= amount`** — there is no balance field. Balance is always aggregated from the ledger.
2. **Forgetting `select_for_update()`** — a balance check without a row lock is a race condition, even inside `transaction.atomic()`. The atomic block alone does not prevent two transactions from reading the same balance.
3. **Putting the simulated bank call inside the lock** — holds the database transaction open during a slow operation. Always commit the state transition first, then make the call, then start a new transaction for the outcome.
4. **Using `Decimal` "to be safe"** — paise are integers. Decimals introduce a different class of bugs (precision config, rounding modes) without solving any problem here.
5. **Storing the balance and "keeping it in sync"** — invariably drifts. Always derive.
6. **Implementing idempotency in-memory or via cache** — must survive process restarts. Database-backed only.
7. **Letting the state machine be enforced "by convention"** — the only enforcement that counts is in `transition_to()`. Anything else gets bypassed.
8. **Catching `IntegrityError` broadly** — catch the specific unique-violation case for idempotency keys. A blanket catch hides real bugs.
9. **Using `django-fsm`** — the PRD explicitly chose hand-rolled state machine. Don't suggest the library.
10. **Using Celery / Redis** — the PRD explicitly chose Django-Q with PostgreSQL broker. Don't suggest Celery.

---

## When unsure

- Re-read `PRD.md`.
- Re-read this file.
- If a question is genuinely ambiguous, ask the human before generating code.
- If a request contradicts these rules, surface the conflict explicitly. Do not silently work around it.

---

## Files to read for full context

1. `PRD.md` — product requirements, data model, API contracts, build order.
2. `EXPLAINER.md` (when written) — the five answers that justify the architecture.
3. `backend/ledger/services.py` — canonical patterns for balance + locking.
4. `backend/payouts/state_machine.py` — canonical pattern for state transitions.

---

## Out of scope (don't suggest these)

- Real bank API integration — settlement is simulated.
- Customer payment ingestion — credits are seeded directly.
- Authentication beyond `X-Merchant-Id` header — this is a take-home, not a product.
- Multi-currency — paise/INR only.
- Mobile responsiveness, dark mode, animations.
- Microservices, event sourcing (unless explicitly chosen as a bonus).
- Test coverage beyond the two required tests + a few high-value extras.
