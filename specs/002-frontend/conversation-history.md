# Conversation History — Feature 002: Frontend

Append-only, cumulative session log (Constitution P3 & P7). Earlier entries are never
overwritten or truncated.

---

## Session 1 — 2026-06-18

**Context / goal:** Kick off the frontend feature (`frontend/` slice) from
`002-frontend-SPEC.md`, under constitution governance, executing phase-by-phase with
user acceptance.

**Pre-flight findings:**
- **P7 fail-closed:** `.active_feature` was **missing**. Resolved by setting it to
  `002-frontend` (gitignored, local-only).
- **P3 gap:** `specs/002-frontend/` had only the input spec; missing `spec.md`,
  `prompts.md`, `conversation-history.md` — created this session.
- Backend currently exposes only `GET /health`; no `docs/api/openapi.json`.

**Decisions made (with reasoning):**
- **D1 — React 19+** (per feature C-01) over `SPEC.md` §5's "React 18". Reasoning: user
  chose the feature spec's newer target; the conflict is logged in
  `docs/architecture.md` and flagged for a **human PR** to fix the master spec (P5
  forbids the AI editing `SPEC.md`).
- **D2 — React Context API** (honor C-02) instead of the Redux-flavored `store/` layout.
  Reasoning: C-02 is an explicit constraint and outranks layout naming; `store/` folder
  kept with Context provider/reducer files, no Redux dependency.
- **D3 — Mock against an assumed REST contract**, toggled by `VITE_USE_MOCKS`.
  Reasoning: the real endpoints don't exist yet; isolating them behind a service layer
  lets the UI be built and swapped to the real backend later (flip base URL).
- **D4 — `CLAUDE.md` + `plan.md` both in `specs/002-frontend/`** per user request. Noted
  that a `CLAUDE.md` there is not auto-loaded and that feature context normally lives in
  `spec.md` (P5).

**Defaults adopted:** Vite build (→ `index.html` at `frontend/` root, deviating from the
spec's `public/index.html`); JWT in memory only (C-09); plain CSS; `TEST_CASES.xlsx` →
`.md`; `SCREENSHOTS/*.png` captured manually post-build.

**Edge cases / unknowns discovered:** exact backend endpoint shapes; whether a UI kit is
wanted; whether the xlsx must be a true binary. Tracked as `[NEEDS CLARIFICATION]` in
`spec.md` §7 (non-blocking).

**`[NEEDS CLARIFICATION]` raised:** 3 (backend contract, UI library, xlsx format).
**Resolved this session:** D1–D4.

**Files altered this session (Phase 0):**
- Set `.active_feature` → `002-frontend`.
- Created `specs/002-frontend/{plan.md, spec.md, CLAUDE.md, prompts.md, conversation-history.md}`.
- Appended Feature-002 decision entry to `docs/architecture.md`.

**Approval state:** `plan.md` approved by user ("approve, start Phase 0"). Phases 1–8
pending, each to stop for acceptance.

---

## Session 1 — 2026-06-18 (Phase 1: Scaffold)

**Context / goal:** Stand up the runnable Vite + React 19 project shell and verify it
builds, lints, and serves (foundation for AC-20/18/19/02).

**Work done:**
- Created `frontend/`: `package.json` (React 19.1, react-router-dom 7, Vite 6, ESLint 9
  + jsx-a11y), `vite.config.js` (`outDir: build`), root `index.html`, `.env.example` +
  local `.env` (`VITE_API_BASE_URL`, `VITE_USE_MOCKS`), `frontend/.gitignore`,
  `eslint.config.js` (flat config), `src/main.jsx`, `src/App.jsx` (placeholder shell),
  `src/index.css` (design tokens + responsive base), `public/favicon.svg` +
  `public/logo.svg`, and `src/assets/{images,icons,styles}/.gitkeep`.

**Decisions / notes:**
- **Binary asset substitution:** spec listed `favicon.ico`/`logo.png`; authored as
  `favicon.svg`/`logo.svg` (text, deterministic, modern) — same rationale as the
  deferred screenshots. Documented for the owner.
- ESLint flat config used (ESLint 9 default); `no-console` set to warn (AC-18 intent).
- Tooling present locally: Node v24.16.0, npm 11.13.0.

**Verification (passed):**
- `npm install` → 280 packages, no errors.
- `npm run build` → built in ~1s, `build/` emitted (index.html + css + js).
- `npm run lint` → clean (no errors/warnings).
- `npm run preview` → HTTP 200 at `localhost:4173`, `#root` present.

**Edge cases discovered:** Windows `Start-Process npm` fails (needs `npm.cmd`); noted for
future run commands. No `[NEEDS CLARIFICATION]` added.

**Files altered:** all under `frontend/` (listed above). No other slice touched.

**Approval state:** Phase 1 complete; awaiting acceptance to start Phase 2 (core infra:
utils, services + mocks, store/ contexts, hooks).
