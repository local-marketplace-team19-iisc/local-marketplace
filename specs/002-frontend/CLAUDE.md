# CLAUDE.md — Feature 002: Frontend (feature-scoped context)

> Feature-scoped AI context for the frontend slice, placed here per the owner's request
> (D4). **This is NOT the root `CLAUDE.md`** (which is human-owned and AI-forbidden to
> edit, Constitution P5) and it is **not auto-loaded** by Claude Code from this path —
> it is an informational companion to `spec.md`/`plan.md`. The root `CLAUDE.md` and
> `specs/constitution.md` still govern and outrank this file.

## What this feature is
React 19 presentation layer (Vite) for the Local Marketplace. Presentation only — no
business logic (C-04). REST integration (C-03), env-configurable (C-05).

## Working rules (recap of constitution, applied here)
- **Slice discipline (P6):** only touch `frontend/**` and the three audit files in
  `specs/002-frontend/`. Append-only to `docs/architecture.md`. Never edit root
  `CLAUDE.md`, `SPEC.md`, `constitution.md`, or `backend/**`.
- **Dry-run (P1):** `plan.md` is approved; execution proceeds phase-by-phase with user
  acceptance between phases.
- **Audit (P3/P7):** append a timestamped entry to `conversation-history.md` at each
  session/milestone; log prompts in `prompts.md`.
- **Secrets (P4):** commit `frontend/.env.example` only; `frontend/.env` is gitignored.

## Stack & conventions
- React 19 + Vite + react-router-dom. State = **React Context API** (`src/store/*Context.jsx`,
  no Redux). Plain CSS + `index.css`. ESLint + jsx-a11y (AC-18/19).
- Services in `src/services/` call REST via `apiClient.js`; **mock layer** in
  `src/services/_mocks/` is toggled by `VITE_USE_MOCKS` (D3).
- JWT in memory only — never browser storage (C-09).

## Commands (run inside `frontend/`)
- Install: `npm install`
- Dev: `npm run dev`
- Build: `npm run build` (AC-20)  ·  Lint: `npm run lint` (AC-18/19)

## Pointers
- Contract & decisions: `spec.md` · Dry-run & phases: `plan.md`
- Assumed API: `spec.md` §6 and `frontend/API_INTEGRATION_GUIDE.md`
