# Playto Pay — Payout Engine

A production-grade payout engine built for the Playto Founding Engineer Challenge. Indian merchants accumulate balance from customer payments and withdraw to bank accounts. The system handles money integrity, concurrent requests, idempotency, and state-machine-driven payout processing.

---

## Live deployment

| Service | URL |
|---|---|
| Frontend | https://django-wallet-fbxh7snwf-godhunt69s-projects.vercel.app/ |
| Backend API | https://django-wallet-production.up.railway.app/api/v1/merchants|

---

## Screenshots


### Dashboard — Balance & Payout Form
![Dashboard](docs/screenshots/dashboard.png)


### Payout History — Status Transitions
![Payment History](docs/screenshots/history.png)


### Ledger Feed
![Ledger Feed](docs/screenshots/ledger.png)

### Railway Setup
![Backend Setup](docs/screenshots/railway.png)


---

## Stack

| Layer | Choice |
|---|---|
| Backend | Django 5.2 + Django REST Framework |
| Database | PostgreSQL 16 |
| Background jobs | Django-Q2 |
| Frontend | React 18 + Vite + Tailwind CSS |
| Local dev | Docker Compose |
| Backend hosting | Railway (web service + worker service + Postgres) |
| Frontend hosting | Vercel |

---

## Local setup

### Prerequisites

- Docker Desktop (running)
- Node.js 20+
- Python 3.12+ with `uv` (`pip install uv`)

### 1. Start backend + worker + database

```bash
docker compose up --build
```

This single command:
- Starts PostgreSQL 16
- Runs Django migrations
- Seeds 3 test merchants with transaction history
- Starts the Django development server on port 8000
- Starts the Django-Q worker for background payout processing

### 2. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

That's it. Two terminals.

---

## Environment variables

The backend reads these from `backend/.env` or the shell environment:

| Variable | Default (dev) | Description |
|---|---|---|
| `DATABASE_URL` | `postgres://playto:playto@localhost:5432/playto` | PostgreSQL connection string |
| `SECRET_KEY` | `dev-only-key-not-for-production` | Django secret key |
| `DEBUG` | `True` | Django debug mode |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins |

---

## Seeded test data

Three merchants are created on first run. Use the dropdown in the dashboard to switch between them.

| Merchant | Email | Starting balance |
|---|---|---|
| Acme Design Studio | acme@test.local | ₹5,00,000 |
| Bharat Freelancers Co | bharat@test.local | ₹1,25,000 |
| Mango Tech LLP | mango@test.local | ₹2,000 |

Each merchant has 2 bank accounts and a backdated credit history visible in the ledger feed.

**Live merchant UUIDs (Railway):**

| Merchant | UUID |
|---|---|
| Acme Design Studio | `24eadaaf-c0e7-4250-a5f2-fa5f83f881b8` |
| Bharat Freelancers Co | `475684bc-36a5-4f7c-8ff9-e17f48777fbf` |
| Mango Tech LLP | `cd8e9b87-4636-425e-ae6b-cfd44f42ddb0` |

---

## API quick reference

All endpoints are prefixed `/api/v1/`. Authenticated endpoints require `X-Merchant-Id: <uuid>`.

### Create a payout

```bash
curl -X POST https://django-wallet-production.up.railway.app/api/v1/payouts \
  -H "Content-Type: application/json" \
  -H "X-Merchant-Id: 24eadaaf-c0e7-4250-a5f2-fa5f83f881b8" \
  -H "Idempotency-Key: $(python -c 'import uuid; print(uuid.uuid4())')" \
  -d '{"amount_paise": 10000, "bank_account_id": "3b09ad20-ef02-40c0-811f-8622cb962f89"}'
```

### Get balance

```bash
curl -H "X-Merchant-Id: 24eadaaf-c0e7-4250-a5f2-fa5f83f881b8" \
  https://django-wallet-production.up.railway.app/api/v1/balance
```

### List payouts

```bash
curl -H "X-Merchant-Id: 24eadaaf-c0e7-4250-a5f2-fa5f83f881b8" \
  "https://django-wallet-production.up.railway.app/api/v1/payouts/list?limit=25&offset=0"
```

### List ledger entries

```bash
curl -H "X-Merchant-Id: 24eadaaf-c0e7-4250-a5f2-fa5f83f881b8" \
  "https://django-wallet-production.up.railway.app/api/v1/ledger?limit=25&offset=0"
```

---

## Running tests

Tests require a live PostgreSQL instance (no SQLite).

```powershell
# PowerShell
$env:DATABASE_URL="postgres://playto:playto@localhost:5432/playto"; uv run pytest -v
```

```bash
# bash/zsh
DATABASE_URL=postgres://playto:playto@localhost:5432/playto uv run pytest -v
```

**24 tests across 4 modules:**

| Module | Tests |
|---|---|
| `idempotency/tests/test_idempotency.py` | 6 — duplicate replay, body conflict, missing key, invalid UUID, in-flight, per-merchant scoping |
| `ledger/tests/test_services.py` | 5 — empty balance, credit/debit math, append-only enforcement, lock requires transaction, field validation |
| `payouts/tests/test_state_machine.py` | 12 — all allowed and forbidden transitions, terminal state enforcement, DB persistence |
| `payouts/tests/test_concurrency.py` | 1 — two threads race to overdraw; exactly one succeeds |

Run the concurrency test in a loop to confirm stability:

```powershell
$env:DATABASE_URL="postgres://playto:playto@localhost:5432/playto"; 1..10 | ForEach-Object { uv run pytest payouts/tests/test_concurrency.py -v }
```

---

## How it works

The backend is split into three separated concerns, each with its own Django app:

```
POST /api/v1/payouts
        │
        ▼
┌─────────────────┐     ┌──────────────────┐
│  idempotency/   │────▶│    payouts/       │
│  Reject dupes   │     │  create_payout()  │
│  before any     │     │  - lock ledger    │
│  business logic │     │  - check balance  │
└─────────────────┘     │  - write DEBIT    │
                        │  - status=PENDING │
                        └────────┬─────────┘
                                 │
                        ┌────────▼─────────┐
                        │    ledger/        │
                        │  LedgerEntry      │
                        │  append-only      │
                        │  balance derived  │
                        │  never stored     │
                        └────────┬─────────┘
                                 │
                    (separate Railway service)
                                 │
                        ┌────────▼─────────┐
                        │  Django-Q Worker  │
                        │  qcluster polls  │
                        │  every 30s        │
                        │  - pick PENDING   │
                        │  - simulate bank  │
                        │  - COMPLETED or   │
                        │    FAILED+REFUND  │
                        └──────────────────┘
```

**Web service** (gunicorn) handles all HTTP requests — balance reads, payout creation, idempotency enforcement. It never processes payouts itself.

**Worker service** (Django-Q qcluster) runs as a completely separate Railway process. It polls the database every 30 seconds, picks up `PENDING` payouts, calls the simulated bank, and settles the outcome. If it crashes, Railway restarts it and pending payouts are picked up on the next poll — no money is lost.

**Ledger** is the single source of truth. Balance is never cached or stored — it's always recomputed from the sum of ledger entries. A `PAYOUT_HOLD` debit is written the moment a payout is created. A `PAYOUT_REFUND` credit is written if it fails. Completed payouts leave the hold permanent.


See [EXPLAINER.md](EXPLAINER.md) for the five decisions that matter:

1. **Ledger** — balance derived by `Sum(Case(...))` aggregation, never stored
2. **Lock** — `SELECT FOR UPDATE` on ledger rows before balance check prevents overdraw
3. **Idempotency** — database unique constraint, insert-first approach, in-flight detection
4. **State machine** — all status writes through `transition_to()`, `FAILED`/`COMPLETED` are terminal
5. **AI audit** — bugs generated by AI assistance, caught in review, and fixed

---

## Project structure

```
playto-payout/
├── backend/
│   ├── manage.py
│   ├── pyproject.toml          # uv dependency management
│   ├── playto/                 # Django project (settings, urls, wsgi)
│   ├── ledger/                 # Merchant, BankAccount, LedgerEntry models + services
│   ├── payouts/                # Payout model, state machine, views, workers
│   ├── idempotency/            # IdempotencyKey model + check/record service
│   └── conftest.py             # pytest fixtures
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Merchant selector, layout
│   │   ├── api.js              # fetch wrapper with header injection
│   │   ├── format.js           # paise→rupees, timestamp, status badge
│   │   └── components/
│   │       ├── BalanceCard.jsx       # 5s polling
│   │       ├── PayoutForm.jsx        # payout creation with idempotency key
│   │       ├── PayoutHistoryTable.jsx # 3s polling, click-to-expand
│   │       └── LedgerFeed.jsx        # 5s polling, load-more pagination
│   ├── vite.config.js
│   └── tailwind.config.js
├── docker-compose.yml
├── Dockerfile                  # root-level, build context = repo root
├── railway.toml                # Railway deployment config
├── vercel.json                 # Vercel deployment config
├── README.md
└── EXPLAINER.md
```
