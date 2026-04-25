Alright, here's the full breakdown. I'll go phase by phase, step by step, with what to build, what to test, what to commit, and what to watch out for.

---

# Phase 1 — Backend core (hours 0–8)

This is the part the reviewer actually grades. Don't move past it until everything works end-to-end via curl.

## Step 1: Project scaffold + settings + Postgres connection (0–1h)

**Goal:** A Django project that boots, connects to Postgres, and answers `/healthz/`. Nothing else.

**Substeps:**

1. `cd backend && uv init` — creates `pyproject.toml` and `.venv`
2. `uv add django djangorestframework django-environ "psycopg[binary]" django-q2 django-cors-headers gunicorn whitenoise`
3. `uv add --dev pytest pytest-django factory-boy ruff`
4. `uv run django-admin startproject playto .` — careful with the trailing dot
5. `uv run python manage.py startapp ledger`, then `payouts`, then `idempotency`
6. Spin up Postgres locally: `docker compose up -d postgres` (using your `docker-compose.yml`)
7. Fill in `playto/settings.py` per the placeholder comments — env-driven, INSTALLED_APPS, REST_FRAMEWORK config, Q_CLUSTER config
8. Add `playto/health.py` and wire it in `playto/urls.py`
9. Run `uv run python manage.py migrate` — this creates Django's built-in tables
10. Run `uv run python manage.py runserver` — visit `http://localhost:8000/healthz/`, should return `{"status": "ok"}`

**Test it works:**
```bash
curl http://localhost:8000/healthz/
# {"status": "ok"}
```

**Commit:** `chore: project scaffold with django, drf, postgres`

**Watch out for:**
- Postgres not accepting connections — check `docker ps` and `docker logs <postgres-container>`. The healthcheck in docker-compose should prevent this but sometimes the first boot is slow.
- Django defaults to SQLite. If you forget to set `DATABASE_URL`, `manage.py migrate` will create `db.sqlite3` and silently work. Add the explicit assertion in settings: `if "postgresql" not in DATABASES["default"]["ENGINE"]: raise ImproperlyConfigured(...)`.
- `django-q2` (the maintained fork), not `django-q` (abandoned). Easy to install the wrong one.

---

## Step 2: Ledger models + services + balance test (1–3h)

**Goal:** A correct, append-only ledger with database-derived balance. This is the foundation everything else sits on.

**Substeps:**

1. Write `ledger/models.py` for `Merchant`, `BankAccount`, `LedgerEntry` per the placeholder spec
2. Write `ledger/exceptions.py` — `InvalidAmount`, `InsufficientBalance`
3. Write `ledger/services.py` with three functions:
   - `get_balance(merchant_id)` — pure read, uses `Coalesce(Sum(Case(When(...))), Value(0))`
   - `get_balance_for_update(merchant_id)` — same but acquires `select_for_update()` lock
   - `credit(...)` and `debit(...)` — create a single LedgerEntry, validate `amount_paise > 0`
4. Override `LedgerEntry.save()` to raise on update: `if self.pk is not None: raise ValueError("LedgerEntry is append-only")`
5. Add the CHECK constraint and composite index in `Meta`
6. `uv run python manage.py makemigrations ledger`
7. `uv run python manage.py migrate`
8. Write `ledger/tests/factories.py` with `MerchantFactory`, `BankAccountFactory`, `LedgerEntryFactory`, plus the `merchant_with_balance(amount_paise)` helper
9. Write `ledger/tests/test_services.py` — at minimum tests 1, 2, 4, 5, 6 from the placeholder
10. Run `uv run pytest ledger/`

**Test it works:**
```python
# In Django shell: uv run python manage.py shell
from ledger.models import Merchant, LedgerEntry
from ledger.services import get_balance, credit

m = Merchant.objects.create(name="Test", email="test@local")
credit(m.id, 100000, "TEST", description="seed")
credit(m.id, 50000, "TEST")
print(get_balance(m.id))  # should print 150000

# Try to update an existing entry — should raise
e = LedgerEntry.objects.first()
e.amount_paise = 999
e.save()  # ValueError: LedgerEntry is append-only
```

**Commit:** `feat(ledger): merchant, bank account, append-only ledger entry with derived balance`

**Watch out for:**
- The `Coalesce` is essential. Without it, an empty ledger returns `None`, and `None - 1000` blows up later. This is one of the AI-audit candidates.
- Don't forget `output_field=BigIntegerField()` on the `Case`/`When` expression. Without it, Django infers the field type from the first match, which can cause subtle issues with negative numbers.
- `select_for_update()` will throw `TransactionManagementError` if called outside `transaction.atomic()`. Test this — it's a feature, not a bug.
- Migrations should be small and committed. If you regenerate `0001_initial.py` three times, that's a sign you're iterating without thinking.

---

## Step 3: Payout model + state machine + state machine tests (3–5h)

**Goal:** A Payout model that can only transition through legal states, tested exhaustively.

**Substeps:**

1. Write `payouts/models.py` for `Payout` per the placeholder — fields, choices, ALLOWED_TRANSITIONS, constraints, indexes
2. Write `payouts/state_machine.py` with `IllegalStateTransition` exception and `transition_to(payout, new_status)` function
3. Write `payouts/exceptions.py` — `BankAccountNotFound`
4. `makemigrations payouts && migrate`
5. Write `payouts/tests/test_state_machine.py` — all 11 tests from the placeholder. Each is 3-5 lines; this should be quick and the file should look like a clear matrix of allowed/blocked transitions.
6. Run `uv run pytest payouts/tests/test_state_machine.py -v`

**Test it works:**
```python
# All these should pass with no errors:
from payouts.models import Payout
from payouts.state_machine import transition_to, IllegalStateTransition
import pytest

p = Payout.objects.create(merchant=m, bank_account=ba, amount_paise=5000)
transition_to(p, "PROCESSING")  # ok
transition_to(p, "COMPLETED")   # ok
with pytest.raises(IllegalStateTransition):
    transition_to(p, "PENDING")  # blocked, terminal
```

**Commit:** `feat(payouts): payout model with strict state machine`

**Watch out for:**
- The state machine should be the ONLY way `payout.status` is written. After this step, do a project-wide grep for `payout.status =` and `\.status = "P` — should return zero hits outside `state_machine.py` and the model file itself.
- Don't add side effects (no signals, no ledger writes) inside `transition_to()`. Side effects are the caller's responsibility.
- `update_fields=["status", "updated_at"]` matters. Without it, `save()` writes every field, which can race with other transactions modifying other fields on the same row.
- `COMPLETED` and `FAILED` are empty sets. Use `set()` not `{}` (the latter is a dict).

---

## Step 4: POST /api/v1/payouts with idempotency + lock (5–7h)

**Goal:** The single most important endpoint in the system. Idempotent, locked, atomic.

**Substeps:**

1. Write `idempotency/models.py` — `IdempotencyKey` with the unique constraint
2. Write `idempotency/exceptions.py` — `MissingIdempotencyKey`, `InvalidIdempotencyKey`, optionally the `IdempotencyResult` enum
3. Write `idempotency/services.py`:
   - `hash_request_body(body)` — canonical JSON + SHA256
   - `check_or_record(merchant_id, key, request_hash)` — returns `(result, record)` tuple
   - `record_response(record, status, body, payout_id)`
   - `expire_old_keys()`
4. `makemigrations idempotency && migrate`
5. Write `payouts/services.py::create_payout(...)` — the lock-check-debit-create flow
6. Write `payouts/serializers.py` — `PayoutCreateSerializer`, `PayoutSerializer`
7. Write `payouts/views.py::CreatePayoutView` — the orchestration of header parsing → idempotency → service call → response recording
8. Wire URLs in `payouts/urls.py` and include in `playto/urls.py`
9. Add CORS middleware config so the frontend can hit it later
10. Test manually with curl

**Test it works:**

```bash
# Get a merchant ID from the shell first:
# uv run python manage.py shell
# >>> from ledger.models import Merchant; Merchant.objects.create(name="A", email="a@a.a"); ...

# Create an idempotency key
KEY=$(uuidgen)
MERCHANT="<paste merchant uuid>"
BANK="<paste bank account uuid>"

# First call → 201
curl -i -X POST http://localhost:8000/api/v1/payouts \
  -H "Idempotency-Key: $KEY" \
  -H "X-Merchant-Id: $MERCHANT" \
  -H "Content-Type: application/json" \
  -d "{\"amount_paise\": 5000, \"bank_account_id\": \"$BANK\"}"

# Second call with same key → 200/201, same payout_id
curl -i -X POST http://localhost:8000/api/v1/payouts \
  -H "Idempotency-Key: $KEY" \
  -H "X-Merchant-Id: $MERCHANT" \
  -H "Content-Type: application/json" \
  -d "{\"amount_paise\": 5000, \"bank_account_id\": \"$BANK\"}"

# Different key, insufficient balance (massive amount) → 402
curl -i -X POST http://localhost:8000/api/v1/payouts \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "X-Merchant-Id: $MERCHANT" \
  -d "{\"amount_paise\": 999999999, \"bank_account_id\": \"$BANK\"}"
```

**Commit:** `feat(payouts): create payout endpoint with idempotency and row-level locking`

**Watch out for:**
- The single biggest mistake: forgetting `select_for_update()` and relying on `transaction.atomic()` alone. Postgres default isolation (READ COMMITTED) lets two concurrent transactions both read the same balance simultaneously. The atomic block is necessary but not sufficient.
- Insert the idempotency key BEFORE doing any business logic. If you do balance check first, then insert, two duplicates can both pass the balance check before the unique constraint fires.
- Catch `IntegrityError` *narrowly*. Inspect `e.__cause__` or check the constraint name. A blanket catch hides real bugs (e.g. a bad foreign key).
- Bank account ownership check: validate that `bank_account.merchant_id == request_merchant_id`. Without this, merchant A can withdraw to merchant B's account.
- The simulated bank call (`time.sleep`) MUST happen outside the transaction. Re-read the placeholder if tempted to put it inside.
- Don't return the merchant_id in the response. Don't return internal IDs that aren't meaningful. Just `payout_id`, `status`, `amount_paise`, `created_at`.

---

## Step 5: Concurrency test + idempotency test (7–8h)

**Goal:** The two required tests, both passing reliably.

**Substeps:**

1. Update `conftest.py` with the `merchant_with_balance` fixture and the Postgres assertion
2. Write `payouts/tests/test_concurrency.py` per the placeholder — `Barrier(2)`, two threads, both attempt 6000-paise withdrawal from a 10000-paise balance
3. Write `idempotency/tests/test_idempotency.py` — at minimum tests 1, 2, 3, 6 from the placeholder
4. Run the concurrency test 10 times in a row to confirm stability:
   ```bash
   for i in {1..10}; do uv run pytest payouts/tests/test_concurrency.py -v || break; done
   ```
5. Run `uv run pytest` to confirm full suite passes

**Test it works:** all tests green, concurrency test passes 10/10 runs.

**Commit:** `test: concurrency and idempotency`

**Watch out for:**
- `pytest-django` default fixture is `db` (transactional, rollback). For concurrency you need `transactional_db` or `@pytest.mark.django_db(transaction=True)` — without this, both threads share one transaction and the test is meaningless.
- `close_old_connections()` in each thread's `finally` block. Django uses thread-local connections; without cleanup, you'll leak connections and break later tests.
- If the concurrency test passes 9/10 times, the lock is broken. Don't accept "mostly passing" — investigate. Usually it's either missing `select_for_update()` or the wrong queryset (locking the wrong rows).
- For the idempotency test, post the request body as JSON (`format="json"` in DRF's APIClient), not as form data. Otherwise the canonical hash won't match.

**At the end of Phase 1, you should be able to answer all four major EXPLAINER questions by pointing at real code.** Don't move on until this is true.

---

# Phase 2 — Backend worker (hours 8–10)

## Step 6: Django-Q setup + process_pending_payouts (8–9h)

**Goal:** A worker process that picks up PENDING payouts, runs the simulated settlement, and transitions them to COMPLETED or FAILED.

**Substeps:**

1. Verify Q_CLUSTER config is in `settings.py` with `orm: "default"` (Postgres-backed broker)
2. `uv run python manage.py migrate django_q` — creates the broker tables
3. Write `payouts/services.py::pickup_pending_payouts(limit)` per placeholder — `select_for_update(skip_locked=True)`, transition to PROCESSING, set `processing_started_at`
4. Write `payouts/services.py::settle_payout(payout_id, outcome)` — inside one atomic block: transition status, create refund credit if failure
5. Write `payouts/workers.py::simulate_bank_settlement()` — random with explicit thresholds (70/20/10)
6. Write `payouts/workers.py::process_pending_payouts()` — loop over picked IDs, call settle outside transaction
7. Write `payouts/management/commands/setup_schedules.py` — register the recurring task
8. Run the worker in a separate terminal: `uv run python manage.py qcluster`
9. Create a payout via curl and watch it move through the lifecycle

**Test it works:**

```bash
# Terminal 1 — server running
uv run python manage.py runserver

# Terminal 2 — worker
uv run python manage.py qcluster

# Terminal 3 — register schedules (once)
uv run python manage.py setup_schedules

# Terminal 3 — create a payout
curl -X POST http://localhost:8000/api/v1/payouts \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "X-Merchant-Id: $MERCHANT" \
  -d '{"amount_paise": 5000, "bank_account_id": "..."}'

# Watch the worker terminal — within a minute, you should see it process
# Verify in the DB:
uv run python manage.py shell
>>> from payouts.models import Payout
>>> Payout.objects.values("status").annotate(count=Count("id"))
# Should show COMPLETED or FAILED
```

**Commit:** `feat(workers): payout processor with django-q`

**Watch out for:**
- `skip_locked=True` is critical when running multiple worker processes. Without it, two workers fight over the same row.
- `select_for_update()` requires being inside `transaction.atomic()`. If you forget, Django raises immediately — good, don't suppress it.
- The simulated bank call must happen OUTSIDE the transaction in `pickup_pending_payouts`. The flow is: open txn → lock → transition to PROCESSING → commit → call bank → open new txn → record outcome → commit.
- Django-Q schedules with minutes=1 means once per minute, not "every 5 seconds." For the challenge's stated 30-second stuck threshold, this means a stuck payout might wait up to 90 seconds before recovery (60s detection + 30s threshold). Document this in the README.
- If the worker dies silently, check the `django_q_failure` table — exceptions go there.

---

## Step 7: recover_stuck_payouts + retry/refund logic (9–10h)

**Goal:** Stuck payouts retry up to 3 times with exponential backoff, then fail and refund.

**Substeps:**

1. Write `payouts/services.py::retry_or_fail(payout_id)` — locks the payout, checks attempt_count, transitions to PENDING (with backoff) or FAILED (with refund)
2. Update `pickup_pending_payouts` query to also pick rows where `processing_started_at` is in the past (so backoff-delayed retries are picked up correctly)
3. Write `payouts/workers.py::recover_stuck_payouts()` — find PROCESSING rows older than 30s, call `retry_or_fail`
4. Write `idempotency/services.py::expire_old_keys()` and wire it as a worker task
5. Update `setup_schedules.py` with all three schedules
6. Add tests in `payouts/tests/test_services.py` for retry behavior (placeholder tests 9, 10, 11)
7. Manual test: create a payout, wait for it to hang (10% probability), watch it retry

**Test it works:**

```python
# In Django shell, simulate a stuck payout:
>>> from payouts.models import Payout
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> p = Payout.objects.filter(status="PROCESSING").first()
>>> # Force it to look stuck
>>> p.processing_started_at = timezone.now() - timedelta(seconds=60)
>>> p.save()
>>> # Within a minute, the worker should pick it up and either retry or fail
```

**Commit:** `feat(workers): stuck payout recovery with exponential backoff`

**Watch out for:**
- The exponential backoff math: attempt 1 → 5s, attempt 2 → 10s, attempt 3 → 20s. After attempt 3, mark FAILED.
- Don't double-refund. The refund happens in `settle_payout` (when bank says "failed") AND in `retry_or_fail` (when max retries exhausted). These are mutually exclusive paths — a payout either gets a definitive bank response or times out. Add a guard: if a refund entry already exists for this payout, don't create another. Or simpler: trust the state machine — once a payout is FAILED, no further state transitions happen, so no second refund.
- The retry-or-fail function locks the payout row. If two recovery workers see the same stuck row simultaneously, one waits, the second sees the already-transitioned state and skips.

---

# Phase 3 — Read endpoints (hours 10–11)

## Step 8: GET endpoints + seed script (10–11h)

**Goal:** All the read endpoints the dashboard needs, plus a one-shot script that seeds test data.

**Substeps:**

1. Write `ledger/views.py::BalanceView` — returns available, held, total credited, total debited
2. Write `ledger/views.py::LedgerListView` — paginated, filtered by merchant
3. Write `payouts/views.py::PayoutListView` and `PayoutDetailView`
4. Write `ledger/serializers.py::LedgerEntrySerializer`, `BalanceSerializer`
5. Add an endpoint or hardcoded list for the frontend to discover seeded merchants. Simplest: `GET /api/v1/merchants` returning id+name only. Or just print them at the end of the seed script and paste into the frontend.
6. Write `payouts/management/commands/seed.py` — 3 merchants, 2 bank accounts each, 4-6 credit entries each, all idempotent (use `get_or_create`)
7. Run `uv run python manage.py seed`, copy the printed UUIDs

**Test it works:**

```bash
curl -H "X-Merchant-Id: $MERCHANT" http://localhost:8000/api/v1/balance
# {"available_paise": 145000, "held_paise": 5000, ...}

curl -H "X-Merchant-Id: $MERCHANT" http://localhost:8000/api/v1/ledger
# Paginated list of credits and debits

curl -H "X-Merchant-Id: $MERCHANT" http://localhost:8000/api/v1/payouts/list
# Paginated list of payouts
```

**Commit:** `feat: read endpoints for balance, ledger, payouts + seed script`

**Watch out for:**
- The `held_paise` calculation: sum of `amount_paise` for payouts in PENDING or PROCESSING. This is for display only; the actual hold is already a DEBIT in the ledger so it's already reflected in `available_paise`. Don't subtract it again.
- Filter by `X-Merchant-Id` on every endpoint. Without this, merchant A can read merchant B's data. This isn't a security feature in the challenge sense (no real auth), but the endpoints should still respect the implicit authorization model.
- Pagination: DRF's default is `LimitOffsetPagination`. Set `PAGE_SIZE = 25` in settings. The frontend's "Load more" button increments offset by 25.
- Seed script must be idempotent. Reviewer might run it twice. Use `get_or_create` keyed on email for merchants, on `(merchant, account_number_masked)` for bank accounts.

---

# Phase 4 — Frontend (hours 11–13)

## Step 9: Vite scaffold + api.js + merchant selector (11–11.5h)

**Goal:** A page that loads, lets you pick a merchant, and successfully calls the backend.

**Substeps:**

1. `cd .. && npm create vite@latest frontend -- --template react`
2. `cd frontend && npm install`
3. `npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p`
4. Configure `tailwind.config.js` content paths and add the three directives to `index.css`
5. Write `src/api.js` — fetch wrapper, all functions per placeholder
6. Write `src/format.js` — paiseToRupees, formatTimestamp, statusBadgeClasses
7. Write `src/App.jsx` — merchant selector, layout grid, localStorage persistence
8. `npm run dev` and verify the merchant dropdown loads from the API

**Test it works:** open `http://localhost:5173`, see a dropdown listing the seeded merchants. Pick one. Open browser devtools and verify the network calls include `X-Merchant-Id`.

**Commit:** `feat(frontend): vite + tailwind scaffold with merchant selector`

**Watch out for:**
- CORS: if the frontend can't reach the backend, check `CORS_ALLOWED_ORIGINS` in Django settings includes `http://localhost:5173`.
- `import.meta.env.VITE_API_URL` requires the `VITE_` prefix or Vite won't expose it.
- `crypto.randomUUID()` requires HTTPS or localhost. On `127.0.0.1` it works; on a non-HTTPS deployed URL it doesn't. Use a polyfill or `uuid` package if deploying somewhere with HTTP.

---

## Step 10: BalanceCard + PayoutForm (11.5–12.5h)

**Goal:** Two components that let the user see their balance and submit a payout.

**Substeps:**

1. Write `src/components/BalanceCard.jsx` — fetch on mount, poll every 5s, pause on hidden tab
2. Write `src/components/PayoutForm.jsx` — controlled inputs, paise conversion, fresh idempotency key per submit, error handling for 402/422/409
3. Wire both into `App.jsx`
4. Submit a payout, watch the balance card update on the next poll

**Test it works:** create a payout for 100 rupees from a merchant with 1000 rupees. Balance card shows 1000 → 900 within 5 seconds.

**Commit:** `feat(frontend): balance card and payout form with idempotency`

**Watch out for:**
- Don't store amount as a number in state. Use a string. `parseFloat("10.5")` works but `parseFloat("10.")` gives 10, which then shows as "10" in the input and you've fought the user.
- Convert to paise with `Math.round(parseFloat(amount) * 100)`. The Math.round is critical — `0.1 * 100 === 10.000000000000002` in JS. Round to integer.
- Reset the form on success but keep the merchant selection.
- Show the resolved paise amount under the input ("10.50 = 1050 paise"). It's a tiny touch that proves you understand the unit.

---

## Step 11: PayoutHistoryTable + LedgerFeed (12.5–13h)

**Goal:** Real-time-ish view of payouts and ledger entries.

**Substeps:**

1. Write `src/components/PayoutHistoryTable.jsx` — table with status badges, polling every 3s
2. Write `src/components/LedgerFeed.jsx` — list with reference-type badges, polling every 5s
3. Wire `refreshTrigger` from `PayoutForm` so the table refreshes immediately after a successful submit (don't wait for the next poll)
4. Test by creating a payout and watching it move through PENDING → PROCESSING → COMPLETED/FAILED in real time. Watch a refund entry appear in the ledger feed when one fails.

**Test it works:** the lifecycle is visible without refreshing the page. Especially: a failed payout shows in the table AS FAILED and the matching refund entry appears in the ledger feed.

**Commit:** `feat(frontend): payout history and ledger feed with polling`

**Watch out for:**
- Polling intervals add up. Three components polling at 5s/3s/5s = a lot of requests. On Railway free tier this might hit limits. Pause polling when the tab is hidden via `document.visibilitychange`.
- Don't optimistically update the table on submit. Just trigger a refetch. The submit might succeed then the worker fails it 30s later — you want the UI to reflect server truth, not optimistic guesses.
- Status badges should not include emojis (per CLAUDE.md). Use Tailwind background colors and clear text.

---

# Phase 5 — Ship (hours 13–15)

## Step 12: Deploy backend to Railway, frontend to Vercel (13–14h)

**Goal:** Working URLs the reviewer can hit.

**Backend (Railway) substeps:**

1. Push your code to GitHub
2. Create a Railway project, add the Postgres addon
3. Create the WEB service from the repo, root `/backend`. Set start command and release command per `railway.toml` placeholder
4. Create the WORKER service from the same repo. Override start command to `python manage.py qcluster`
5. Set env vars on both services. Critical ones: `DJANGO_SECRET_KEY` (long random string), `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS` (your Railway domain), `CORS_ALLOWED_ORIGINS` (your Vercel domain — you'll have to come back and set this after Vercel deploys)
6. Wait for first deploy to finish. Run seed: `railway run --service backend python manage.py seed`. Capture the printed UUIDs
7. Run setup_schedules: `railway run --service backend python manage.py setup_schedules`
8. Hit `/healthz/` on the deployed URL — should return 200

**Frontend (Vercel) substeps:**

1. Import the GitHub repo. Set root directory to `frontend`. Vercel auto-detects Vite
2. Set env var `VITE_API_URL` to the Railway backend URL (with `https://`)
3. Deploy
4. Go back to Railway and update `CORS_ALLOWED_ORIGINS` to include the Vercel URL
5. Restart the Railway web service

**Test it works:** open the Vercel URL, pick a merchant, request a payout, watch it process. Open the Railway worker logs and watch the payout settle.

**Commit:** `chore: deployment configs for railway and vercel`

**Watch out for:**
- Railway free tier sleeps after inactivity. The worker might miss schedules if the whole project sleeps. Document this in the README.
- The release command runs migrations AND setup_schedules. If setup_schedules fails (e.g. duplicate schedule), the deploy fails. Make setup_schedules idempotent (`update_or_create`).
- `DJANGO_ALLOWED_HOSTS` must include exactly the hostname Railway gives you. Wildcard doesn't work in production.
- HTTPS is required for `crypto.randomUUID()` to work in some browsers. Vercel and Railway both serve HTTPS by default.
- If the worker container can't reach Postgres, check that the `DATABASE_URL` env var is set on the worker service too (Railway doesn't automatically share env vars across services in the same project).

---

## Step 13: README + EXPLAINER + final commit cleanup (14–15h)

**Goal:** The reviewer can set up, run, and understand your code in five minutes.

**Substeps:**

1. Write `README.md` per the placeholder structure: stack, setup, env vars, seeded data UUIDs, API examples, test commands, deployed URLs
2. Write `EXPLAINER.md` per the placeholder. For each of the five questions: short prose + code paste + trade-off note. Use real code from your repo, not paraphrased.
3. For question 5 (AI audit), pick the strongest example from your `ai-audit-notes.md` scratch file. The best ones are the ones where the AI's bug would have caused real harm if shipped — wrong locking, Python-side balance arithmetic, transaction-held-during-network-call.
4. Squash trivial WIP commits. Make sure `git log --oneline` reads as a coherent story. The reviewer reads it.
5. Final smoke test: clone fresh in `/tmp`, follow your README from scratch, see if it works.
6. Submit the form: GitHub URL, deployed URL, "what you're most proud of" note

**The "most proud of" note:** keep it specific. Not "the architecture" — say something like "the EXPLAINER question 5 catches a real bug in AI-generated code that would have caused balance corruption under concurrent load. The fix is in commit X." Concrete and demonstrable beats abstract.

**Final commit:** `docs: README and EXPLAINER for review`

**Watch out for:**
- Don't paraphrase code in the EXPLAINER. Paste exact lines with file paths. The reviewer should be able to grep your repo for what you cite.
- Each EXPLAINER answer should be 3–5 sentences plus the code snippet. Anything longer is rambling. The reviewer reads dozens of these.
- Don't apologize for trade-offs. Frame them as deliberate: "I chose 409-on-in-flight over blocking-wait because..."
- Test the README by handing your repo URL to a friend who's never seen it. If they can't run it in 10 minutes, your README needs work.

---

# Cross-cutting practices (do these throughout)

**Keep `ai-audit-notes.md` open from minute one.** Every time AI gives you something subtly wrong, paste the bad version + your fix immediately. By Step 13 you'll have a real list to pick from for EXPLAINER question 5. Strongest candidates: missing `select_for_update`, Python-side balance math, transaction held during network call, `Decimal` instead of integer paise, broad `IntegrityError` catch, missing `Coalesce` for empty ledger.

**Run the concurrency test in a loop after every change to lock-related code.** `for i in {1..10}; do pytest payouts/tests/test_concurrency.py || break; done`. If it ever fails, the lock is broken. Don't move on.

**Commit after every step, not at the end.** The reviewer reads `git log` to assess your thinking. A repo with one giant "initial commit" looks like you copy-pasted from somewhere.

**Don't add features beyond the spec.** Webhooks, audit logs, event sourcing — all are bonus and almost certainly not worth the time. Better to nail the five core EXPLAINER answers than to half-finish a sixth feature.

**When stuck on a Django specifics, default to `transaction.atomic()` + `select_for_update()`.** If your gut says "this might race," it does. Add the lock.

That's the full plan. Pick up at Step 1 when you're ready to start, and ping me when you hit any specific blocker — concurrency tests not stabilizing, deployment headaches, EXPLAINER wording, anything.