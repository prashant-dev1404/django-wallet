# Playto Pay — Payout Engine

A submission for the Playto Founding Engineer Challenge 2026.

> **Status:** scaffolding stage. Implementation plan in `PRD.md`. AI agent rules in `CLAUDE.md`.

---

## TODO when implementing this README

Replace this section with:

1. **One-paragraph description** of what the service does (merchant ledger + payout engine).
2. **Stack summary** in a table (Django, DRF, PostgreSQL, Django-Q, React, Tailwind).
3. **Local setup**:
   - Prerequisites (Python 3.12+, Node 20+, Docker, PostgreSQL 15+)
   - `docker-compose up -d` for Postgres
   - Backend: `cd backend && uv sync && uv run python manage.py migrate && uv run python manage.py seed`
   - Worker: `uv run python manage.py qcluster`
   - Frontend: `cd frontend && npm install && npm run dev`
4. **Environment variables** needed (`DATABASE_URL`, `DJANGO_SECRET_KEY`, `VITE_API_URL`, etc.)
5. **Seeded test data** — list the 3 merchants and their starting balances, with example IDs the reviewer can paste into the dashboard merchant selector.
6. **API examples** — one curl for `POST /api/v1/payouts` showing the `Idempotency-Key` header.
7. **Running tests** — `uv run pytest`, plus a note that the concurrency test needs `--reuse-db` disabled.
8. **Deployed URLs** — backend on Railway, frontend on Vercel.
9. **Pointers** — link to `PRD.md` for design, `EXPLAINER.md` for the five answers.

Keep it tight. The reviewer is judging code quality, not README prose.
