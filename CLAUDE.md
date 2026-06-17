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

## Overrides
This file is committed and shared. Put machine-specific tweaks in `CLAUDE.local.md`
(gitignored).
