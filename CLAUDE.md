# CLAUDE.md — Local Marketplace

Authority (read in this order; conflicts resolve upward)

specs/constitution.md — supreme, non-negotiable rules.
SPEC.md — master product spec + the runnable app scaffold.
docs/architecture.md — living decision log (filled per feature; may be empty early).

Stack

Python 3.11 · FastAPI + uvicorn · pydantic-settings · pytest + httpx · ruff · Docker.
Later: PostgreSQL + PostGIS + pgvector. Config via env (.env); secrets never committed.

Commands

Install: make install
Run: make dev → uvicorn app.main:app --app-dir backend --port ${PORT:-8000}
Test: make test (pytest) · Lint: make lint (ruff check .)
Health: GET /health → 200 {"status":"ok"}

## Working rules (from the constitution)
- Dry-run first: never create/modify implementation files until that feature's
  `plan.md` is written and approved.
- One feature = one folder; only touch the current feature's slice; files owned by
  another feature are off-limits.
- Idempotent writes: check if a file exists before writing. For governance/config
  files (`constitution.md`, `pyproject.toml`, `.gitignore`, this file) append/merge
  missing sections — never overwrite.
- Audit trail: each feature keeps `spec.md`, `prompts.md`, `conversation-history.md`;
  remove secrets before committing them.
- No secrets in source: `.env` is gitignored; commit only `.env.example` (placeholders).
- Unambiguous specs: mark unknowns `[NEEDS CLARIFICATION]` — never guess.

## Frontend (Feature 002)
React 19 presentation layer (Vite) for the Local Marketplace. Presentation only — no
business logic (C-04). REST integration (C-03), env-configurable (C-05).

Stack & conventions
- React 19 + Vite + react-router-dom. State = **React Context API** (`src/store/*Context.jsx`,
  no Redux). Plain CSS + `index.css`. ESLint + jsx-a11y (AC-18/19).
- Services in `frontend/src/services/` call REST via `apiClient.js`; **mock layer** in
  `src/services/_mocks/` is toggled by `VITE_USE_MOCKS` (D3).
- JWT in memory only — never browser storage (C-09).
- Commit `frontend/.env.example` only; `frontend/.env` is gitignored (P4).

Commands (run inside `frontend/`)
- Install: `npm install`
- Dev: `npm run dev`
- Build: `npm run build` (AC-20)  ·  Lint: `npm run lint` (AC-18/19)

Pointers
- Contract & decisions: `specs/002-frontend/spec.md` · Dry-run & phases: `specs/002-frontend/plan.md`
- Assumed API: `specs/002-frontend/spec.md` §6 and `frontend/FRONTEND_DOCUMENTATION.md` §4

## Overrides
This file is committed and shared. Put machine-specific tweaks in `CLAUDE.local.md`
(gitignored).
