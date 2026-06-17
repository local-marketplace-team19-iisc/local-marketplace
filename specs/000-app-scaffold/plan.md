# Plan — Feature 000: App Scaffold (Dry-Run)

> Iron-Clad Rule (Constitution P1 / SPEC §8): this dry-run must be **reviewed and
> approved by the user** before any implementation file is created or modified.
> Feature 000 is governed but **not** a product feature; it has **no `spec.md`** —
> the master `SPEC.md` is its spec (Constitution P3 exemption).

## Scope

Deliver the one-time runnable starting point that satisfies **SPEC §7** acceptance
criteria only. No product features (catalog, vendors, search, orders, auth, db,
frontend) — those are `later` rows in §5 and are out of scope here.

## Acceptance criteria being targeted (SPEC §7)

1. App boots via the run command and serves on `localhost:$PORT`.
2. `GET /health` → `200` with body exactly `{"status":"OK"}`.
3. Setting `PORT=9001` rebinds the server to 9001.
4. **No route other than `/health` exists.**
5. `pytest` passes (`backend/tests/test_health.py`); `ruff check .` is clean.
6. (optional) `docker compose up` serves `/health` with `200`.

## Files to CREATE

| Path | Purpose |
| :-- | :-- |
| `backend/app/__init__.py` | package marker |
| `backend/app/main.py` | `FastAPI()` app; mounts health router; `__main__` runs uvicorn on `settings.PORT` |
| `backend/app/core/__init__.py` | package marker |
| `backend/app/core/config.py` | `Settings` via `pydantic-settings`; `PORT: int = 8000` (reads `PORT` env) |
| `backend/app/api/__init__.py` | package marker |
| `backend/app/api/routes/__init__.py` | package marker |
| `backend/app/api/routes/health.py` | `GET /health` → `{"status":"OK"}` |
| `backend/tests/__init__.py` | package marker |
| `backend/tests/test_health.py` | asserts criteria 2 (and 4: docs routes 404) via `httpx`/TestClient |
| `pyproject.toml` | pinned deps + `ruff` + `pytest` config; `requires-python >=3.11` |
| `.env.example` | `PORT=8000` (placeholder only — Constitution P4) |
| `Dockerfile` | python:3.11-slim image running the app |
| `docker-compose.yml` | single `backend` service (Docker is optional per §5) |
| `Makefile` | `run`, `test`, `lint` targets |
| `docs/architecture.md` | created **empty** (§4: filled incrementally, never pre-populated) |
| `specs/000-app-scaffold/prompts.md` | audit trail (Constitution P3) |
| `specs/000-app-scaffold/conversation-history.md` | audit trail (Constitution P3) |

## Files to MODIFY (append/merge only — Constitution P6)

| Path | Change |
| :-- | :-- |
| `.gitignore` | append `.env` (P4: `.env` must be gitignored; currently absent) |
| `README.md` | append a "Run / Test" section under the existing title |

## Files explicitly NOT touched

- `CLAUDE.md` — **exists; human-owned; AI forbidden to modify (Constitution P5).**
  If the team wants scaffold notes in it, a human must add them via PR.
- `specs/constitution.md`, `SPEC.md` — governing docs, not changed by execution.
- All `later` paths: `backend/app/schemas|models|db`, `backend/migrations`,
  `db/init/01-extensions.sql`, `frontend/`, `docs/api/openapi.json`.

## Key execution decisions (resolving scaffold-level unknowns)

1. **Criterion 4 ("no route other than `/health`")** — FastAPI mounts `/docs`,
   `/redoc`, `/openapi.json` by default. Decision: construct
   `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` so only `/health`
   exists. The test will assert these return `404`. *(This resolves prior review
   finding **H** at the scaffold level. The §4 "generated openapi.json" is a
   `later` concern; programmatic export via `app.openapi()` remains possible then.)*
2. **Criterion 3 (PORT rebinds)** — run command is `python -m backend.app.main`,
   whose `__main__` calls `uvicorn.run(app, host="0.0.0.0", port=settings.PORT)`.
   `pydantic-settings` reads `PORT` from env, so `PORT=9001 python -m backend.app.main`
   binds 9001. The Makefile `run` target wraps this.
3. **Body casing** — `{"status":"OK"}` exactly (uppercase), per current §7.
4. **Python** — `requires-python >=3.11`; local runtime is 3.13 (satisfies).

## Pinned dependencies (pyproject.toml)

- runtime: `fastapi`, `uvicorn[standard]`, `pydantic-settings`
- dev: `pytest`, `httpx`, `ruff`
- Exact versions pinned at write time (latest stable compatible with py3.11).

## Architectural risks

- **R1** — Disabling `openapi_url` now means the `later` "exported OpenAPI contract"
  (§4) must re-enable/generate it explicitly. Acceptable; flagged for feature 001+.
- **R2** — `host="0.0.0.0"` in Docker vs `127.0.0.1` locally; acceptance says
  `localhost`, which `0.0.0.0` serves. Low risk.
- **R3** — None of the product unknowns (N/O/P/Q from review) are in scope; they
  remain `[NEEDS CLARIFICATION]` for product features and do not block 000.

## Verification steps (post-implementation, Phase VALIDATE)

1. `make run` (or `python -m backend.app.main`) → `curl localhost:8000/health` = `{"status":"OK"}`.
2. `PORT=9001 python -m backend.app.main` → `curl localhost:9001/health` = `200`.
3. `curl localhost:8000/docs` → `404` (criterion 4).
4. `pytest` green; `ruff check .` clean.
5. (optional) `docker compose up` → `/health` = `200`.

---
**STATUS: AWAITING APPROVAL.** No implementation file will be created or modified
until this plan is approved.
