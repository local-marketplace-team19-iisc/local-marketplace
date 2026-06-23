# Plan — Feature 007: Deployment (Dry-Run)

> **Iron-Clad Rule (Constitution P1 / SPEC §8):** this dry-run MUST be reviewed and
> **approved by the user** before any implementation file is created or modified.

---

## Scope

**In scope:**
- `requirements.txt` at repo root (Vercel Python runtime dependency list)
- `api/index.py` — Vercel serverless entry point that re-exports the FastAPI `app`
- `vercel.json` — build config + routing rules (API → Python function; all else → SPA)
- `.env.example` — append Supabase and CORS variable placeholders
- `.claude/mcp.json` — Supabase MCP registration (HTTP/SSE transport, project-scoped)
- `backend/app/db/session.py` — switch to `NullPool` + 7-second command timeout for serverless compatibility
- `docs/architecture.md` — append deployment topology decision

**Out of scope:**
- Changing any existing feature's business logic, routes, or schema
- CI/CD pipeline (GitHub Actions) — deferred
- Custom domain / SSL certificate — handled in Vercel dashboard by the user
- Alembic migration files — schema is unchanged; only the target DB URL changes

---

## Files to CREATE

| Path | Purpose |
| :-- | :-- |
| `./requirements.txt` | Vercel Python runtime deps at **repo root** (see spec §6 for exact contents) |
| `./api/index.py` | `from backend.app.main import app` — Vercel ASGI entry point |
| `./vercel.json` | `buildCommand: "cd frontend && npm install && npm run build"`, `outputDirectory: "frontend/dist"`, API + SPA rewrites |
| `./.claude/mcp.json` | Supabase MCP registration (HTTP/SSE, project-scoped) |

---

## Files to MODIFY (append/merge only — Constitution P6)

| Path | Change |
| :-- | :-- |
| `.env.example` | Append: `DATABASE_URL`, `DATABASE_URL_DIRECT`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `CORS_ORIGINS` |
| `backend/app/db/session.py` | Add `NullPool` import; add `connect_args={"command_timeout": 7}` and `poolclass=NullPool` to `create_async_engine`; gate it on `VERCEL=1` env var so local Docker still uses the default pool |
| `frontend/.env.example` | Append: `VITE_API_URL=`, `VITE_USE_MOCKS=false` (if not already present) |
| `docs/architecture.md` | Append ADR: "007 — Vercel + Supabase deployment topology" |

---

## Files explicitly NOT touched

- `CLAUDE.md` — human-owned; AI forbidden to modify (Constitution P5)
- `specs/constitution.md`, `SPEC.md` — governing docs
- Any file owned by features 001-006 except `backend/app/db/session.py` (shared infra, surgical change gated on env var)
- `pyproject.toml` — unchanged; `requirements.txt` is an additional artifact for Vercel, not a replacement

---

## Key execution decisions

1. **No `mangum` adapter.** Vercel's `@vercel/python` runtime supports ASGI directly. `api/index.py` simply re-exports `app`; no adapter shim needed.

2. **`NullPool` gated on `VERCEL=1`.** Vercel automatically sets `VERCEL=1` in its build and runtime environment. The session module checks this env var so local Docker runs keep their connection pool.

3. **Two connection strings.** `DATABASE_URL` → pooled (port 6543, `?pgbouncer=true`) for runtime. `DATABASE_URL_DIRECT` → direct (port 5432) for Alembic. The `alembic.ini` `sqlalchemy.url` line is replaced with `%(DATABASE_URL_DIRECT)s` in `env.py`.

4. **`geoalchemy2` / `shapely` excluded from `requirements.txt`.** These require GDAL/GEOS system binaries absent on Vercel Lambda. Existing vendor spatial queries are converted to `sqlalchemy.text()` raw PostGIS SQL during this feature.

5. **MCP config committed.** `.claude/mcp.json` is committed because it contains only the public MCP endpoint URL and the project ref (a non-secret identifier visible in the Supabase dashboard URL). No key material is stored there.

6. **`vercel.json` build command — frontend only.**

   `buildCommand` compiles the React SPA only. The FastAPI backend requires **no build step**: Vercel detects `api/index.py`, reads `./requirements.txt`, installs the Python deps, and deploys the function as a Lambda automatically — no script needed.

   | Concern | How Vercel handles it | Explicit step in `buildCommand`? |
   | :-- | :-- | :-- |
   | Backend deps | Auto-reads `./requirements.txt` | No |
   | Backend boot | Wraps `api/index.py` as a Lambda | No |
   | Frontend bundle | Must be told to run `vite build` | **Yes** |

   **Canonical `vercel.json`:**
   ```json
   {
     "buildCommand": "cd frontend && npm install && npm run build",
     "outputDirectory": "frontend/dist",
     "installCommand": "echo skip",
     "rewrites": [
       { "source": "/api/(.*)", "destination": "/api/index.py" },
       { "source": "/(.*)",     "destination": "/index.html"   }
     ]
   }
   ```

   - `buildCommand` — `cd frontend && npm install && npm run build` runs `vite build` (from `frontend/package.json`), outputs to `frontend/dist/`
   - `outputDirectory` — `frontend/dist` is where Vite writes the compiled SPA
   - `installCommand: "echo skip"` — prevents Vercel from running `npm install` at the repo root (no root `package.json`)
   - `rewrites` — `/api/*` routed to the Lambda; everything else served from the SPA

---

## Architectural risks

| ID | Risk | Mitigation |
| :-- | :-- | :-- |
| R-1 | `geoalchemy2`/`shapely` C deps absent on Vercel | Excluded from `requirements.txt`; spatial queries use raw SQL |
| R-2 | Cold start > 3 s (large bundle) | Exact version pins; no dev deps in `requirements.txt` |
| R-3 | DB call hits 10-second Vercel limit | `command_timeout=7` + HTTP 503 before hard kill |
| R-4 | Alembic DDL breaks against pooler | `env.py` uses `DATABASE_URL_DIRECT` (port 5432) |
| R-5 | Preview deployments have wrong CORS origin | `CORS_ORIGINS` env var set per-environment in Vercel dashboard |

---

## Execution phases

### Phase 0 — Supabase MCP: register & authenticate

Goal: select the Supabase MCP server, complete browser-based OAuth, and confirm Claude Code can query the remote project before any code or config is written.

**Step 0.1 — Register the MCP server (writes `.claude/mcp.json`):**
```bash
claude mcp add --scope project --transport http supabase \
  "https://mcp.supabase.com/mcp?project_ref=hstezspiljhcuhjraitb"
```
- `--scope project` → config written to `.claude/mcp.json` in this repo (committed, non-secret)
- `--transport http` → HTTP/SSE transport; the MCP server pushes events over the SSE stream

**Step 0.2 — Confirm the server is listed:**
```bash
claude mcp list
# Expected: supabase   http   https://mcp.supabase.com/mcp?project_ref=hstezspiljhcuhjraitb
```

**Step 0.3 — Authenticate (browser OAuth flow):**
The first tool call against the `supabase` MCP triggers Supabase's OAuth flow. Claude Code will print a URL — open it in a browser, log in with the Supabase account that owns project `hstezspiljhcuhjraitb`, and grant access. The token is stored in Claude Code's local credential store (never in the repo).

Trigger authentication by asking Claude Code to use the MCP:
> "Use the supabase MCP tool to list the tables in the project."

Claude Code will open the auth URL automatically (or print it if running headless). Complete the browser login to receive the OAuth callback.

**Step 0.4 — Verify the connection:**
After authentication, confirm the MCP can reach the Supabase project:
> "Use the supabase MCP tool to list all tables in the public schema."

Expected: Claude returns the table list from the live Supabase project (`users`, `vendors`, etc.).

**Gate check — must pass before Phase 1:**
- [ ] `claude mcp list` shows `supabase` with `http` transport
- [ ] OAuth flow completed without error
- [ ] MCP tool call returns the correct schema (tables visible, no auth error)

---

### Phase 1 — Local Vercel dev (`vercel dev`)

Goal: confirm the full stack works end-to-end locally through the Vercel CLI before any production push.

**Prerequisites (one-time, done by the developer):**
```bash
npm i -g vercel          # install Vercel CLI
vercel login             # authenticate
vercel link              # link repo to the Vercel project (creates .vercel/project.json)
```

`.vercel/` is gitignored by Vercel CLI automatically.

**Run local dev:**
```bash
vercel dev               # starts at http://localhost:3000 by default
```

`vercel dev` simulates the full Vercel runtime locally:
- Serves the React SPA via Vite's dev server (hot reload)
- Runs Python serverless functions from `api/` in a local sandbox that mirrors the Lambda environment (same Python version, same `requirements.txt`)
- Reads env vars from `.env` (root) — the same file used by local Docker; no separate `.env.vercel` needed

**Gate checks (must all pass before Phase 2):**

1. `pip install -r requirements.txt` in a clean Python 3.11 venv — no errors
2. `vercel dev` starts without build errors
3. `GET http://localhost:3000/api/health` → `{"status":"ok"}` (health router mounted at `/api` prefix; confirms Lambda boots)
4. `GET http://localhost:3000/` → React SPA loads (confirms frontend routing)
5. `GET http://localhost:3000/any-frontend-route` → SPA catch-all serves `index.html`
6. `POST http://localhost:3000/api/auth/register` with valid payload → writes to Supabase, returns JWT
7. `alembic upgrade head` (using `DATABASE_URL_DIRECT`) — migrations apply cleanly against Supabase
8. `claude mcp list` → shows `supabase` with `http` transport
9. `make lint` + `npm run lint` — both clean

---

### Phase 2 — Production push (`vercel --prod`)

Proceed only after **all Phase 1 gate checks pass**.

**Before pushing:**
- Set all env vars listed in spec §7 in the Vercel dashboard under *Settings → Environment Variables* for the **Production** environment
- Confirm `CORS_ORIGINS` is set to the final production URL (e.g. `https://<project>.vercel.app`)

**Deploy:**
```bash
vercel --prod            # promotes current build to the Production deployment
```

**Post-deploy verification (production):**

1. `GET https://<project>.vercel.app/api/health` → `{"status":"ok"}` within 10 s (cold start)
2. `GET https://<project>.vercel.app/` → React SPA loads
3. `GET https://<project>.vercel.app/some-frontend-route` → SPA catch-all works
4. `POST https://<project>.vercel.app/api/auth/register` → writes to Supabase, returns JWT
5. Vercel dashboard → *Functions* tab → no runtime errors in logs

---

**STATUS: APPROVED.** No implementation file will be created or modified
until this plan is approved by the user.
