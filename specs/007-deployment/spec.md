---
title: Feature 007: Deployment
feature: 007-deployment
status: draft
created: 2026-06-23
---

# Feature 007: Deployment — Specification

> Architectural contract for feature `007-deployment` (Constitution P3).
> Outranked by `specs/constitution.md` and the master `SPEC.md`.

---

## 1. User Scenarios & Edge Cases

### S-1 · Developer deploys the full stack to Vercel
- *Given* the repo is connected to a Vercel project and all environment variables are set in the Vercel dashboard
- *When* a push is made to the `main` branch
- *Then* Vercel builds the React frontend (via `npm run build` in `frontend/`) and deploys the FastAPI backend as Python serverless functions under `/api/*`; both are live at the same Vercel domain within minutes
- **Edge cases:** missing env var causes build-time error with a clear log message; a Python dep with a C extension unavailable on Vercel fails the build → risk R-1 lists mitigations

### S-2 · End user hits the API
- *Given* the Vercel deployment is live
- *When* a browser request reaches `https://<project>.vercel.app/api/health` (health router mounted at `/api` prefix in `main.py`)
- *Then* the FastAPI serverless function cold-starts (≤ 3 s), connects to Supabase via the pooled connection string, returns `{"status": "ok"}` within the 10-second free-tier limit
- **Edge cases:** Supabase pooler is overloaded → DB call times out before Vercel cuts the function; handled with a 7-second SQLAlchemy `connect_args` timeout that returns HTTP 503 before Vercel fires its own 10-second kill

### S-3 · Developer uses Claude Code + Supabase MCP during development
- *Given* `.claude/mcp.json` is present with the Supabase HTTP/SSE entry
- *When* Claude Code runs a tool call against `supabase` MCP
- *Then* Claude can inspect tables, run queries, and apply migrations on the remote Supabase project without exposing the raw service-role key in prompts
- **Edge cases:** MCP server unreachable (VPN/firewall) → tool call returns an error; Claude does not fall back to guessing schema

---

## 2. Functional Requirements & Decisions

| ID | Requirement | Decision & Rationale |
| :-- | :-- | :-- |
| FR-1 | MUST deploy FastAPI as Vercel Python serverless functions | Entry point `api/index.py` exports the FastAPI `app`; Vercel `@vercel/python` runtime picks it up automatically. No `mangum` adapter needed — Vercel's runtime speaks ASGI natively. |
| FR-2 | MUST deploy React (Vite) frontend as Vercel static hosting | `vercel.json` sets `outputDirectory: "frontend/dist"` and `buildCommand: "cd frontend && npm install && npm run build"`. The SPA catch-all rewrite (`/* → /index.html`) is included. |
| FR-3 | MUST create `requirements.txt` at repo root for Vercel Python runtime | Derived from `pyproject.toml` `[project].dependencies`; Vercel reads `requirements.txt` (not pyproject.toml). Includes core deps + `mcp` SDK + `supabase` client. See §6 for the exact file. |
| FR-4 | MUST configure Supabase as the production database | Replace local PostgreSQL with Supabase. Two connection strings are required: (a) pooled `postgresql+asyncpg://.../postgres?pgbouncer=true` on port **6543** (Transaction mode — for runtime API calls); (b) direct `postgresql+asyncpg://.../postgres` on port **5432** (for Alembic migrations only). |
| FR-5 | MUST keep all DB calls under 7 seconds | SQLAlchemy `create_async_engine` is initialised with `connect_args={"command_timeout": 7}` and `pool_class=NullPool` (no persistent pool — serverless functions are stateless). This leaves 3 s margin before Vercel's 10-second free-tier cut. |
| FR-6 | MUST configure Claude Code Supabase MCP with HTTP/SSE transport | Command: `claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp?project_ref=hstezspiljhcuhjraitb"`. Writes `.claude/mcp.json`. `--scope project` scopes it to this repo only. |
| FR-7 | MUST NOT commit secrets | All Supabase keys, JWT secrets, and DB connection strings live in `.env` (gitignored) and in Vercel's Environment Variables UI. Only `.env.example` is committed. |
| FR-8 | SHOULD remove `geoalchemy2` and `shapely` from Vercel build deps | Vercel's Lambda runtime does not include GDAL/GEOS binaries. Spatial queries will use raw PostGIS SQL via SQLAlchemy `text()` instead. `geoalchemy2` and `shapely` stay in `pyproject.toml` for local/Docker use but are excluded from `requirements.txt`. |
| FR-9 | MUST configure CORS to allow the Vercel frontend origin | `allow_origins` in `backend/app/main.py` already accepts configurable origins; add `VITE_API_URL` / `CORS_ORIGINS` env vars to the Vercel project so each preview deployment gets the right origin. |
| FR-10 | MUST add `vercel.json` routing rules | Routes: all `/api/*` requests go to the Python function; all other paths serve the React SPA. |

---

## 3. Success / Acceptance Criteria

- [ ] `GET https://<project>.vercel.app/api/health` returns `{"status":"ok"}` with HTTP 200 within 10 s on a cold start
- [ ] `GET https://<project>.vercel.app/` serves the React SPA (200, `text/html`)
- [ ] `GET https://<project>.vercel.app/some-frontend-route` also serves the SPA (SPA catch-all works)
- [ ] `POST /api/auth/register` successfully writes a row to Supabase and returns a JWT — verifiable end-to-end
- [ ] Alembic migrations run cleanly against Supabase's direct connection (port 5432)
- [ ] `make lint` (`ruff check .`) is clean; `npm run lint` in `frontend/` is clean
- [ ] No secrets appear in committed files (`git log` and `git grep` show no keys)
- [ ] `.claude/mcp.json` exists and `claude mcp list` shows `supabase` with HTTP transport
- [ ] Vercel build log shows zero "package not found" or "binary not found" errors

---

## 4. DB Schema Entities

No new entities are introduced by this feature. This feature migrates the existing schema (defined in features 001, 003, 005, 006) to run on **Supabase PostgreSQL 16** with the following notes:

| Concern | Detail |
| :-- | :-- |
| PostGIS extension | Supabase enables PostGIS by default — no migration change needed |
| pgvector extension | Supabase enables pgvector by default — no migration change needed |
| Spatial columns | Existing `GEOMETRY(POINT, 4326)` columns in `vendor` table remain; queries switch from GeoAlchemy2 ORM expressions to raw `ST_*` SQL via `text()` on Vercel |
| Migration target | `alembic upgrade head` runs against `DATABASE_URL` pointing to Supabase port 5432 (direct, not pooler) |

---

## 5. Requirement Completeness / Definition of Done

This feature is DONE only when **all** hold:

- [ ] No unresolved `[NEEDS CLARIFICATION]` markers remain (Constitution P2)
- [ ] `plan.md` was written and **user-approved** before any implementation file was created (P1)
- [ ] All Functional Requirements (§2) have passing tests or are verified by the acceptance criteria in §3
- [ ] `requirements.txt` exists at repo root and `pip install -r requirements.txt` succeeds in a clean Python 3.11 venv
- [ ] `vercel.json` and `api/index.py` are committed and the Vercel preview URL is green
- [ ] `.claude/mcp.json` is committed (it contains no secrets — only the public MCP endpoint URL and project ref)
- [ ] `.env.example` is updated with all new Supabase variable names
- [ ] `make lint` green · `npm run lint` green
- [ ] Audit trail current: `spec.md`, `plan.md`, `prompts.md`, `conversation-history.md` all committed (P3)
- [ ] `docs/architecture.md` updated with the deployment topology decision

---

## 6. Canonical `./requirements.txt` (repo root)

Placed at `./requirements.txt` — the Vercel Python runtime looks for `requirements.txt` at the project root, not inside a subdirectory. `frontend/package.json` drives the frontend build separately via the `buildCommand` in `vercel.json`.

Derived from `pyproject.toml` `[project].dependencies` with the following changes:
- **Removed:** `geoalchemy2`, `shapely` (no GDAL on Vercel Lambda — FR-8)
- **Removed:** `pgvector` (Supabase has the extension server-side; the Python client is not needed for raw SQL)
- **Removed:** `passlib[bcrypt]` — `passlib` is never imported anywhere in the codebase; `backend/app/security/password.py` calls the `bcrypt` package API directly (`bcrypt.hashpw`, `bcrypt.checkpw`, `bcrypt.gensalt`)
- **Added:** `bcrypt==4.2.1` — explicit pin for the package `security/password.py` imports directly; replaces the transitive-only install via `passlib`
- **Added:** `mcp` — official Anthropic MCP Python SDK
- **Added:** `supabase` — Supabase Python client
- **Pinned:** `asyncpg==0.30.0` (was an unpinned range `>=0.29`; pinned for reproducible builds)
- **Not added:** agent deps (`pyyaml`, `openai`, `httpx`, `redis`, `faster-whisper`, `pillow`, `pytesseract`) — `backend.agent` is CLI-only; `main.py` never imports it, so these are not in the Lambda path
- **Not added:** frontend deps — 004-frontend is pure React/JS; all deps live in `frontend/package.json`

```
# ── Core API ──────────────────────────────────────────────────────────────────
fastapi==0.115.5
uvicorn[standard]==0.32.1
pydantic==2.10.4
pydantic-settings==2.6.1
email-validator==2.2.0

# ── Database (Supabase / PostgreSQL) ─────────────────────────────────────────
sqlalchemy==2.0.36
asyncpg==0.30.0
alembic==1.14.0
psycopg[binary]==3.2.10
supabase>=2.10.0

# ── Auth / Security ───────────────────────────────────────────────────────────
python-jose[cryptography]==3.3.0
bcrypt==4.2.1

# ── MCP SDK ───────────────────────────────────────────────────────────────────
mcp>=1.9.0
```

---

## 7. Environment Variables

### Backend (Vercel Environment Variables + local `.env`)

| Variable | Example value | Notes |
| :-- | :-- | :-- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres.[ref]:[pw]@aws-0-us-east-1.pooler.supabase.com:6543/postgres?pgbouncer=true` | Pooled (Transaction mode) — used by the running API |
| `DATABASE_URL_DIRECT` | `postgresql+asyncpg://postgres.[ref]:[pw]@db.[ref].supabase.co:5432/postgres` | Direct — used by `alembic upgrade head` only |
| `SUPABASE_URL` | `https://hstezspiljhcuhjraitb.supabase.co` | Supabase project REST URL |
| `SUPABASE_ANON_KEY` | `eyJ...` | Public anon key (safe to expose to browser if needed) |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJ...` | **Secret** — server-side only, never in frontend |
| `SECRET_KEY` | `<random 32-byte hex>` | JWT signing key |
| `PORT` | `8000` | Ignored on Vercel (runtime manages the port) |
| `CORS_ORIGINS` | `https://<project>.vercel.app` | Comma-separated allowed origins |

### Frontend (Vite — prefix `VITE_`)

| Variable | Example value | Notes |
| :-- | :-- | :-- |
| `VITE_API_URL` | `https://<project>.vercel.app` | Base URL for REST calls; empty = same origin |
| `VITE_USE_MOCKS` | `false` | Disable mock layer in production |

---

## 8. Architectural Risks

| ID | Risk | Mitigation |
| :-- | :-- | :-- |
| R-1 | C-extension deps (`geoalchemy2`, `shapely`) fail to build on Vercel Lambda | Excluded from `requirements.txt` (FR-8); spatial queries use raw SQL |
| R-2 | Cold start > 3 s due to large dependency bundle | Pin exact versions; exclude dev deps (`pytest`, `ruff`, `httpx`) from `requirements.txt` |
| R-3 | Vercel 10-second timeout on DB-heavy endpoints | `NullPool` + 7-second `command_timeout` returns HTTP 503 gracefully before hard kill |
| R-4 | Supabase MCP project ref exposed in `.claude/mcp.json` | Project ref is a non-secret identifier (same as in the public Supabase URL); only service-role key is secret and stays in `.env` |
| R-5 | Alembic migrations run against pooler (breaks DDL) | `alembic.ini` / `env.py` must use `DATABASE_URL_DIRECT` (port 5432), not the pooled string |
