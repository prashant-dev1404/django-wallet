# Running test-forge against payout-engine

This repo is set up so that [test-forge](../test-forge) can crawl it and generate
Supertest + Playwright tests. Quick guide below.

## One-time setup

1. **Boot the backend.** From this repo's root:

   ```bash
   docker compose up -d postgres backend
   ```

   Wait for `http://localhost:8000/healthz/` to return `OK`.

2. **Seed deterministic test fixtures.** Generated tests reference a fixed
   merchant UUID, so the seed must be deterministic:

   ```bash
   docker compose exec backend python manage.py forge_seed
   ```

   This creates a merchant with UUID `00000000-0000-0000-0000-000000000001`
   and a bank account with UUID `00000000-0000-0000-0000-000000000010`.

3. **Set up test-forge env.** In the test-forge repo:

   ```bash
   cp /path/to/playto-payout/backend/.env.test-forge.example .env
   # Fill in your GROQ_API_KEY (or set NODE_ENV=production + ANTHROPIC_API_KEY)
   ```

## Running forge

From the test-forge repo:

```bash
# Either of these works — both will detect Django:
npx ts-node scripts/forge.ts \
    --target /path/to/playto-payout \
    --base-url http://localhost:8000

# Or, more explicit (recommended if --target root behaves unexpectedly):
npx ts-node scripts/forge.ts \
    --target /path/to/playto-payout/backend \
    --base-url http://localhost:8000
```

forge will:

1. Detect Django via `manage.py` (or `requirements.txt` at root).
2. Crawl `**/urls.py`, `**/views.py`, `**/models.py` to build an APIMap.
3. Call the configured LLM (Groq Llama 70B in dev, Anthropic Claude in prod)
   to plan a test strategy, then generate Supertest + Playwright files.
4. Write generated tests into `test-forge/generated/api/` and
   `test-forge/generated/e2e/`. Review before committing.

## API surface forge will see

| Method | Path | Auth |
|---|---|---|
| POST | `/api/v1/payouts` | `X-Merchant-Id`, `Idempotency-Key` |
| GET | `/api/v1/payouts/list` | `X-Merchant-Id` |
| GET | `/api/v1/payouts/<uuid:pk>` | `X-Merchant-Id` |
| GET | `/api/v1/balance` | `X-Merchant-Id` |
| GET | `/api/v1/ledger` | `X-Merchant-Id` |
| GET | `/api/v1/merchants` | none |
| GET | `/api/v1/bank-accounts` | `X-Merchant-Id` |
| GET | `/healthz/` | none |

## Files added for test-forge compatibility

- `requirements.txt` (root) — flat dep list so test-forge's framework
  detection works when pointed at the repo root.
- `backend/requirements.txt` — same, for tools that don't run uv.
- `backend/payouts/management/commands/forge_seed.py` — deterministic seed
  with fixed merchant + bank account UUIDs.
- `backend/.env.test-forge.example` — env file pinning fixture UUIDs and
  base URL.
- `TEST_FORGE.md` — this file.
