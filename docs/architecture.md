# Architecture Decision Log — Local Marketplace

Living decision log (SPEC §4 / §8). Filled incrementally per feature; append-only —
never pre-populated, never truncated. Newest entries appended below.

---

## Feature 002 — Frontend (2026-06-18)

React presentation layer (`frontend/` slice). Decisions:

- **D1 — React 19+** for the frontend (feature spec C-01).
  - ⚠️ **Conflict with master `SPEC.md` §5**, which states "React 18". This entry is the
    record of that divergence. Resolution requires a **human PR** to update `SPEC.md` §5
    (AI is forbidden from editing `SPEC.md`/root `CLAUDE.md` per Constitution P5). Until
    reconciled, `SPEC.md` §5 and this feature disagree by design/decision.
- **D2 — State management: React Context API + `useReducer`** (C-02). The `src/store/`
  folder is retained but contains Context providers/reducers, not Redux slices. No Redux
  dependency is introduced.
- **D3 — Backend integration via a mocked, assumed REST contract.** The backend
  currently exposes only `GET /health`; no `docs/api/openapi.json` exists. The frontend
  service layer is toggled by `VITE_USE_MOCKS` and points at `VITE_API_BASE_URL`. The
  assumed contract is documented in `specs/002-frontend/spec.md` §6 and
  `frontend/API_INTEGRATION_GUIDE.md`. When the backend publishes real endpoints, flip
  the toggle/base URL — no UI changes required.
- **Build tooling — Vite** (React 19; CRA deprecated). Consequence: `index.html` lives
  at the `frontend/` root (Vite convention), deviating from the input spec's
  `public/index.html` drawing. `public/` holds static assets.
- **Auth/token handling — JWT in memory only** (Constitution-aligned with C-09: no
  sensitive data in browser storage). Session is lost on refresh; the production target
  is an httpOnly cookie issued by the backend, deferred to the auth/backend feature.

Open items (tracked in `specs/002-frontend/spec.md` §7): backend endpoint confirmation,
optional UI component library, and whether `TEST_CASES` must be a true `.xlsx`.
