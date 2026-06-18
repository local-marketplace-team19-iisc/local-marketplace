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

---

## Session 1 — 2026-06-18 (Phase 2: Core infra)

**Context / goal:** Build the non-visual foundation: config/utilities, REST service
layer with the mock dispatcher (D3), Context providers/reducers (D2), and hooks.

**Work done (all under `frontend/src/`):**
- `utils/`: `constants.js` (env-driven `API_BASE_URL`/`USE_MOCKS`, `API_ROUTES`, `ROUTES`,
  `ROLES`, `PRODUCT_CATEGORIES`, `CURRENCY`), `helpers.js` (`formatPrice` ₹/2dp,
  `formatDate`, `classNames`, `truncate`, `sleep`, `uid`, `toErrorMessage`),
  `validators.js` (login/register/product validators → AC-05).
- `services/`: `apiError.js` (shared `ApiError`), `apiClient.js` (fetch wrapper +
  in-memory `setAuthToken`/`getAuthToken` per C-09 + `USE_MOCKS` branch), the five
  services (`auth/product/search/chatbot/order`), and `_mocks/` (`mockData.js` seed +
  token helpers; `index.js` dispatcher implementing the full §6 contract incl. vendor
  CRUD, cheapest-first search, chat, and order placement with inventory decrement).
- `store/`: `authContext.jsx`, `productContext.jsx` (catalog + favorites + multi-vendor
  cart + orders), `chatbotContext.jsx` (in-memory session history → AC-12), `store.jsx`
  (`AppProviders` tree). All Context + `useReducer`, **no Redux** (D2).
- `hooks/`: `useAuth`, `useProducts`, `useChat` (context accessors with guards).
- Wired `AppProviders` into `App.jsx`.

**Decisions / notes:**
- **`store/` filenames** are `*Context.jsx` (not `*Slice.js`) — the explicit D2 reframe.
  Folder name `store/` retained per the spec layout.
- **In-memory JWT enforced**: token set into `apiClient` on login, cleared on logout;
  never persisted (C-09). Refresh ends the session (documented limitation).
- **Mock demo accounts** seeded: `customer@demo.com` / `vendor@demo.com` (pw `demo1234`)
  — to be documented in `API_INTEGRATION_GUIDE.md` (Phase 8).
- Cart spans vendors; `placeOrder` returns one order number + decrements mock stock
  (master SPEC §3 behaviour).

**Verification (passed):** `npm run lint` clean; `npm run build` ok (44 modules, ~1.1s).

**Edge cases / unknowns:** none new. No `[NEEDS CLARIFICATION]` added.

**Files altered:** new `src/utils/*`, `src/services/**`, `src/store/*`, `src/hooks/*`;
modified `src/App.jsx`. No other slice touched.

**Approval state:** Phase 2 complete; awaiting acceptance to start Phase 3 (common
components + routing: Button/Loader/Modal/Navbar, AppRoutes + ProtectedRoute).

---

## Session 1 — 2026-06-18 (Phase 3: Common components + routing)

**Context / goal:** Shared UI primitives and the routing skeleton, including the auth
guard (AC-08), so the app shell is navigable.

**Work done (`frontend/src/`):**
- `components/common/`: `Button.jsx`+css (variants/sizes/loading), `Loader.jsx`+css
  (role=status, reduced-motion aware → AC-03/19), `Modal.jsx`+css (Escape + real
  `<button>` backdrop for a11y-clean close), `Navbar.jsx`+css (role/auth-aware links,
  cart badge, responsive toggle menu → AC-02/07).
- `routes/`: `ProtectedRoute.jsx` (redirects unauthenticated → /login, supports
  role-gating; preserves `from` location), `AppRoutes.jsx` (full route table per
  `ROUTES`; pages render a temporary `Placeholder` until built in Phases 4–7; vendor
  route is role-gated; `*` → home).
- `App.jsx`: composed `AppProviders > BrowserRouter > Navbar + AppRoutes`.

**Decisions / notes:**
- **Routing-first skeleton:** `AppRoutes` uses an inline `Placeholder` for not-yet-built
  pages so routing + the guard are verifiable now; each later phase swaps in the real
  page (one import line per page).
- **Modal close UX:** backdrop is a real `<button>` (keyboard-operable) instead of a
  click-handled `<div>`, keeping jsx-a11y clean while preserving click-outside-to-close.

**Verification (passed):** `npm run lint` clean; `npm run build` ok (62 modules, ~3s);
`npm run preview` → HTTP 200, `#root` present.

**Edge cases / unknowns:** none new. No `[NEEDS CLARIFICATION]` added.

**Files altered:** new `src/components/common/*`, `src/routes/*`; modified `src/App.jsx`.
No other slice touched.

**Approval state:** Phase 3 complete; awaiting acceptance to start Phase 4 (Auth:
Login/Register pages + useAuth wiring; AC-06/07/08).

---

## Session 1 — 2026-06-18 (Phase 4: Auth)

**Context / goal:** Implement the authentication surface — register, login, and
redirect-back after a protected-route bounce (AC-06/07/08).

**Work done (`frontend/src/`):**
- `assets/styles/forms.css`: shared form primitives (`.form-input/.form-error/
  .form-banner`, etc.) reused by auth + later vendor/product forms (AC-05).
- `pages/auth.css`: auth card/layout + role-selector styling.
- `pages/LoginPage.jsx`: validated login form, error banner, loading state; redirects to
  `location.state.from` (set by `ProtectedRoute`) or home (AC-07/08). Shows demo creds.
- `pages/RegisterPage.jsx`: validated registration with a customer/vendor radiogroup;
  vendors land on `/vendor`, customers on `/` (AC-06).
- `routes/AppRoutes.jsx`: swapped the `/login` and `/register` placeholders for the real
  pages.

**Decisions / notes:**
- Field-level a11y: every input has a `<label htmlFor>`, `aria-invalid`, and
  `aria-describedby` wiring to its error/hint (AC-05/19). Forms use `noValidate` so our
  validators (not the browser) own messaging.
- Errors come from the auth context (`error`); the submit `catch` is intentionally empty
  (no console noise → AC-18).

**Verification (passed):** `npm run lint` clean; `npm run build` ok (69 modules, ~3s).
Interactive login/redirect flow to be captured in Phase 8 screenshots (needs a browser).

**Edge cases / unknowns:** none new.

**Files altered:** new `src/assets/styles/forms.css`, `src/pages/auth.css`,
`src/pages/LoginPage.jsx`, `src/pages/RegisterPage.jsx`; modified
`src/routes/AppRoutes.jsx`. No other slice touched.

**Approval state:** Phase 4 complete; awaiting acceptance to start Phase 5 (Customer:
Search/Product/Favorites/Orders pages + product components; AC-09/10).
