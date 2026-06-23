# Conversation History — Feature 007: Deployment

Append-only, cumulative log of every working session on this feature
(Constitution P3 & P7). Earlier entries are NEVER overwritten or truncated.
Each entry: context/goal · decisions + reasoning · edge cases / unknowns ·
`[NEEDS CLARIFICATION]` raised or resolved · files altered.

---

## 2026-06-23 — Session 1: Feature scaffolding

- **Context / goal:** Initialise feature `007-deployment` via `/spec-create`.
- **Decisions:** Created `specs/007-deployment/` with `spec.md`, `plan.md`, `prompts.md`,
  `conversation-history.md`; set `.active_feature` → `007-deployment` (P7).
- **Unknowns raised:** spec.md & plan.md seeded with `[NEEDS CLARIFICATION]` markers
  to be resolved with the user before any implementation (P1, P2).
- **Files altered:** new feature folder + `.active_feature`.

---

## 2026-06-23 — Session 2: Spec authoring

- **Context / goal:** Fill `spec.md` and `plan.md` for Vercel full-stack deployment with Supabase (PostgreSQL) via MCP and strict serverless timeout compliance.
- **Decisions made:**
  - FastAPI deployed as Vercel Python serverless via `api/index.py` (no `mangum` — Vercel ASGI support is native)
  - React/Vite frontend deployed as Vercel static hosting from `frontend/dist`
  - `requirements.txt` created at repo root; `pyproject.toml` unchanged (Vercel reads `requirements.txt`, not pyproject)
  - `geoalchemy2` and `shapely` excluded from `requirements.txt` (no GDAL/GEOS on Vercel Lambda); spatial queries rewritten to raw `text()` SQL in this feature
  - `NullPool` + 7-second `command_timeout` for serverless DB connections; gated on `VERCEL=1` env var so Docker local dev is unaffected
  - Two Supabase connection strings: pooled port 6543 for API runtime, direct port 5432 for Alembic migrations
  - Supabase MCP registered via `claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp?project_ref=hstezspiljhcuhjraitb"`; `.claude/mcp.json` committed (project ref is non-secret)
  - `mcp>=1.9.0` and `supabase>=2.10.0` added to `requirements.txt`
- **Edge cases / risks captured:** R-1 (C deps), R-2 (cold start), R-3 (timeout), R-4 (Alembic vs pooler), R-5 (CORS on preview deployments)
- **[NEEDS CLARIFICATION] resolved:** all markers resolved in this session — spec is complete
- **Files altered:** `specs/007-deployment/spec.md`, `specs/007-deployment/plan.md`, `specs/007-deployment/prompts.md`, `specs/007-deployment/conversation-history.md`

---

## 2026-06-23 — Session 3: Plan update — two-phase execution

- **Context / goal:** User requested the execution flow be split into two explicit phases: local validation with `vercel dev` before any production push with `vercel --prod`.
- **Decisions made:**
  - Replaced the flat "Verification steps" section with two named phases in `plan.md`
  - Phase 1 (`vercel dev`): 9 gate checks that must all pass locally before proceeding; `vercel dev` reads `.env` from root (same as Docker), no extra env file needed
  - Phase 2 (`vercel --prod`): gated on Phase 1 passing; includes pre-push checklist (env vars set in Vercel dashboard) and 5 post-deploy checks against the live production URL
  - One-time prerequisites (`npm i -g vercel`, `vercel login`, `vercel link`) documented; `.vercel/` dir is gitignored automatically by the CLI
- **Unknowns raised/resolved:** none — plan remains complete and unambiguous
- **Files altered:** `specs/007-deployment/plan.md`, `specs/007-deployment/conversation-history.md`

---

## 2026-06-23 — Session 4: Plan update — Phase 0 MCP auth

- **Context / goal:** User requested an explicit MCP selection and authentication step before any code or local dev work begins.
- **Decisions made:**
  - Added Phase 0 before Phase 1 in `plan.md`; phases are now 0 → 1 → 2
  - Phase 0 covers four steps: (1) `claude mcp add` to register the server and write `.claude/mcp.json`; (2) `claude mcp list` to confirm registration; (3) OAuth browser flow triggered by the first tool call; (4) verification via a live schema query through the MCP
  - Auth token is stored in Claude Code's local credential store — never in the repo (Constitution P4)
  - Phase 0 has its own gate check (3 items) that must pass before Phase 1 can begin
- **Unknowns raised/resolved:** none
- **Files altered:** `specs/007-deployment/plan.md`, `specs/007-deployment/conversation-history.md`

---

## 2026-06-23 — Session 5: Clarify file locations

- **Context / goal:** User confirmed exact placement of the two key dependency files.
- **Decisions made:**
  - `./requirements.txt` — at repo root; Vercel Python runtime reads it from there
  - `frontend/package.json` — frontend deps live here; `vercel.json` `buildCommand` runs `cd frontend && npm install && npm run build` which picks it up; no root-level `package.json` involved in the frontend build
  - Updated Files to CREATE table in `plan.md` to use explicit `./` paths throughout
  - Updated key decision #6 in `plan.md` to call out that Vercel reads `frontend/package.json` via the `buildCommand`, not a root `package.json`
  - Updated spec §6 heading to `./requirements.txt (repo root)` with an explicit note
- **Files altered:** `specs/007-deployment/plan.md`, `specs/007-deployment/spec.md`, `specs/007-deployment/conversation-history.md`

---

## 2026-06-23 — Session 6: Derive Vercel build command from Dockerfile

- **Context / goal:** User asked to derive the correct Vercel build command by reading the Dockerfile.
- **Findings from Dockerfile:**
  - Backend `Dockerfile` runs `pip install .` (setuptools package install from `pyproject.toml`) — Vercel cannot replicate this directly
  - Vercel auto-installs Python deps from `./requirements.txt` when processing `api/index.py`; no explicit build command needed for the backend
  - No `pip install .` needed on Vercel because Vercel adds the project root to `sys.path`, making `from backend.app.main import app` importable without a dist-package
  - `Dockerfile` `CMD ["python", "-m", "backend.app.main"]` maps to `api/index.py` exporting `app`
  - Frontend has no build step in the Dockerfile; Vite is used directly → `npm run build` → `vite build` → `frontend/dist`
- **Decisions made:**
  - `vercel.json` `buildCommand`: `"cd frontend && npm install && npm run build"` (must `cd frontend` because `package.json` is at `frontend/package.json`)
  - `vercel.json` `outputDirectory`: `"frontend/dist"`
  - `vercel.json` `installCommand`: `"echo skip"` (no-op; prevents Vercel from trying `npm install` at root)
  - `vercel.json` `rewrites`: `/api/(.*)` → `/api/index.py`; `(.*)` → `/index.html` (SPA catch-all)
- **Files altered:** `specs/007-deployment/plan.md`, `specs/007-deployment/conversation-history.md`

---

## 2026-06-23 — Session 7: Correct buildCommand — frontend only

- **Context / goal:** User clarified that `buildCommand` compiles the frontend only. The FastAPI backend needs no build or boot script in `vercel.json`.
- **Decision:** Vercel auto-detects `api/index.py`, reads `./requirements.txt`, installs Python deps, and deploys the function as a Lambda — all without any entry in `buildCommand`. Writing `pip install -r requirements.txt` in `buildCommand` was wrong and removed.
- **Final `buildCommand`:** `cd frontend && npm install && npm run build`
- **Files altered:** `specs/007-deployment/plan.md`, `specs/007-deployment/conversation-history.md`
