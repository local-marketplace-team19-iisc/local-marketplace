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

---

## Session 1 — 2026-06-18 (Phase 5: Customer features)

**Context / goal:** Build the customer shopping surface — search, product details,
favorites, and the multi-vendor cart → order flow (AC-09/10).

**Work done (`frontend/src/`):**
- `components/products/`: `ProductCard` (+css) showing the AC-10 fields (name, price,
  vendor, rating, availability) with favorite + add-to-cart; `ProductList` (+css)
  responsive grid + empty state; `ProductDetails` (+css) with qty selector + actions.
- `pages/`: `SearchPage` (+`search.css`) with search bar, loader, results; `ProductPage`
  (fetch by `:id`); `FavoritesPage`; `OrdersPage` (+`orders.css`) — cart, checkout
  (single order number across vendors), and order history; confirmation banner.
- `index.css`: added shared `.badge`/`.page-title` styles.
- `AppRoutes.jsx`: `/` and `/search` → SearchPage; `/product/:id` → ProductPage;
  `/favorites`, `/orders` → real pages (still protected).

**Decisions / notes:**
- **Data-fetching pattern:** pages call the **service modules directly** inside effects
  (`getProduct`, `searchProducts`, `listOrders`) using local state, while the Product
  **context** handles cart/favorites/order mutations (event-driven). This deliberately
  avoids a render loop that would arise from depending on the context's non-memoized
  action functions in `useEffect`, and keeps `react-hooks/exhaustive-deps` warning-free.
  `runSearch`/`loadOrders` are wrapped in `useCallback` for the same reason.
- Search results omit `vendorId`; the mock order endpoint resolves items by `productId`,
  so add-to-cart from search works correctly.

**Verification (passed):** `npm run lint` clean; `npm run build` ok (83 modules, ~3.3s).
Click-through (search → cart → place order) to be captured in Phase 8 screenshots.

**Edge cases / unknowns:** none new.

**Files altered:** new `src/components/products/*`, `src/pages/{SearchPage,ProductPage,
FavoritesPage,OrdersPage}.jsx` + `search.css`/`orders.css`; modified `src/index.css`,
`src/routes/AppRoutes.jsx`. No other slice touched.

**Approval state:** Phase 5 complete; awaiting acceptance to start Phase 6 (Chatbot:
ChatWindow/ChatInput/MessageBubble + useChat; AC-11/12).

---

## Session 1 — 2026-06-18 (Phase 6: Chatbot)

**Context / goal:** Conversational search UI rendering API replies with session-
persistent history (AC-11/12).

**Work done (`frontend/src/`):**
- `components/chatbot/`: `MessageBubble` (+css; user/bot/error styling, renders bot
  product listings as links → AC-11), `ChatInput` (submit-on-Enter, clears on send),
  `ChatWindow` (+css; renders history, typing Loader, auto-scrolls to latest).
- `pages/ChatbotPage.jsx`: hosts ChatWindow.
- `AppRoutes.jsx`: `/chat` → ChatbotPage (placeholder removed).

**Decisions / notes:**
- History persists for the session via the Chatbot context's in-memory `messages`
  (AC-12); messages keyed by `uid`. `aria-live="polite"` on the message list for a11y.
- Errors from the chat service are pushed as an error bubble (AC-04) — no console noise.

**Verification (passed):** `npm run lint` clean; `npm run build` ok (90 modules, ~3.5s).
Remaining placeholders: only `/dashboard` and `/vendor` (Phase 7).

**Edge cases / unknowns:** none new.

**Files altered:** new `src/components/chatbot/*`, `src/pages/ChatbotPage.jsx`; modified
`src/routes/AppRoutes.jsx`. No other slice touched.

**Approval state:** Phase 6 complete; awaiting acceptance to start Phase 7 (Vendor:
Dashboard + VendorPage product CRUD; AC-13/14/15).

---

## Session 1 — 2026-06-18 (Phase 7: Vendor)

**Context / goal:** Vendor surface — product CRUD and an inventory overview, both
vendor-gated (AC-13/14/15).

**Work done (`frontend/src/`):**
- `pages/VendorPage.jsx`: lists the vendor's own products (filtered by `user.vendorId`);
  add/edit via a Modal form (validated → AC-05), delete via a confirmation Modal
  (AC-13/14/15). Responsive grid "table" that collapses to labelled cards on mobile.
- `pages/Dashboard.jsx`: inventory stat cards (products, units, out-of-stock, inventory
  value) + link to manage products.
- `pages/vendor.css`: table/stat-card/responsive styles.
- `routes/AppRoutes.jsx`: `/dashboard` and `/vendor` now role-gated (`ROLES.VENDOR`) to
  the real pages; removed the now-unused `Placeholder` helper.
- `components/common/Navbar.jsx`: vendors now see Dashboard + Products links.

**Decisions / notes:**
- Consistent with Phase 5, vendor pages fetch via `productService` directly (local state,
  `useCallback` loaders) and mutate via the service, reloading after each change.
- Two Modal usages exercised: the add/edit form and a delete confirmation (no native
  `window.confirm`, keeping UX/a11y consistent).

**Verification (passed):** `npm run lint` clean; `npm run build` ok (95 modules, ~2.8s);
`npm run preview` → HTTP 200. **All routes now resolve to real pages** (no placeholders).

**Edge cases / unknowns:** none new.

**Files altered:** new `src/pages/{VendorPage,Dashboard}.jsx` + `vendor.css`; modified
`src/routes/AppRoutes.jsx`, `src/components/common/Navbar.jsx`. No other slice touched.

**Approval state:** Phase 7 complete; awaiting acceptance to start Phase 8 (Docs +
finalize: README, UI_DESIGN, COMPONENT/ROUTING/API docs, TEST_CASES.md, SCREENSHOTS
placeholder, Dockerfile; final build/lint + responsiveness review).

---

## Session 1 — 2026-06-18 (Phase 8: Docs + finalize)

**Context / goal:** Produce the §5 output docs, containerization, and run the final
verification — closing out the feature.

**Work done (`frontend/`):**
- Docs: `README.md`, `UI_DESIGN.md`, `COMPONENT_DOCUMENTATION.md`,
  `ROUTING_DOCUMENTATION.md`, `API_INTEGRATION_GUIDE.md` (assumed contract + JWT/mocks),
  `TEST_CASES.md` (AC-01…20 mapping), `SCREENSHOTS/README.md` (capture instructions).
- Containerization: `Dockerfile` (multi-stage Node→nginx), `nginx.conf` (SPA fallback),
  `.dockerignore`.

**Decisions / notes:**
- **Binary deliverable substitutions (as flagged in plan):** `TEST_CASES.xlsx` →
  `TEST_CASES.md`; `SCREENSHOTS/*.png` → manual capture (instructions provided).
- **Docker image build NOT verified locally:** the Docker daemon was not running in this
  environment (`docker build` failed to connect). The Dockerfile/nginx.conf are provided
  and reference the correct `build/` output + `package-lock.json`, but the image build is
  **unverified** — to be confirmed where a daemon is available.

**Verification (passed):** `npm run lint` clean; `npm run build` ok (95 modules, ~2.7s,
JS ~85 kB gzip → AC-20/16). Secrets check: `git check-ignore` confirms `frontend/.env`
and `node_modules` are ignored (P4). All §5 output files present.

**Acceptance criteria status:** AC-18/19 (lint/a11y rules) and AC-20 (build) verified
automatically; AC-01–17 are implemented and verifiable via the browser checklist in
`TEST_CASES.md` (manual click-through + screenshots pending a human run).

**Edge cases / unknowns:** Docker build unverified (daemon down). Open
`[NEEDS CLARIFICATION]` from `spec.md` §7 remain (backend contract, UI-kit, xlsx) —
non-blocking.

**Files altered:** new `frontend/{README,UI_DESIGN,COMPONENT_DOCUMENTATION,
ROUTING_DOCUMENTATION,API_INTEGRATION_GUIDE,TEST_CASES}.md`, `frontend/Dockerfile`,
`frontend/nginx.conf`, `frontend/.dockerignore`, `frontend/SCREENSHOTS/README.md`.
No other slice touched.

**Approval state:** **Phase 8 complete — all 9 phases (0–8) of `plan.md` executed.**
Frontend feature implementation is done pending: (a) manual browser verification +
screenshots, (b) Docker image build on a host with a running daemon, (c) human PR to
reconcile `SPEC.md` §5 React 18→19 (R1) and to promote any shared rules to root CLAUDE.md.

---

## Session 2 — 2026-06-19 (Browser verification)

**Context / goal:** User asked to see manual browser verification. Drove the running app
in a real browser and captured evidence (closes item (a) above).

**Method:** Started the Vite dev server (`npm run dev`, mock mode). Drove the system
**Microsoft Edge** via `playwright-core` (channel `msedge`; no browser download) with a
headless script exercising the end-to-end flows and capturing console/page errors.

**Results — PASS (all flows, zero console/page errors):**
- Login (customer `customer@demo.com`) → redirect to `/`.
- Search "tomato" → 2 cards, **cheapest-first** (₹28.50 then ₹32.00); each card shows
  name/price/vendor/rating/availability (AC-09/10).
- Add to cart → Orders → Place order → "Order placed — ORD-… · total ₹28.50" (single
  order number, AC; master SPEC §3).
- Chatbot "milk" → bot reply with a cheapest-first listing (AC-11/12).
- Vendor login → Dashboard stats (2 products, 65 units, ₹3972.50 value).
- Vendor CRUD: ADD (rows 2→3) → EDIT (price → ₹55.00) → DELETE (rows 3→2)
  (AC-13/14/15).
- **AC-18 confirmed:** `CONSOLE_ERRORS: []`, `PAGE_ERRORS: []` across the whole run.

**Screenshots captured** to `frontend/SCREENSHOTS/`: `Login.png`, `Search.png`,
`Chatbot.png`, `Dashboard.png`, `VendorDashboard.png`.

**Findings / notes:**
- In-memory JWT + cart (C-09) means a full page reload ends the session — confirmed
  (initial script used `page.goto` and got bounced to login). Real-user SPA navigation
  works correctly; documented behaviour, not a defect.
- `LoginPage` always redirects to the intended/home route; only `RegisterPage`
  role-routes to `/vendor`. Vendors reach vendor screens via the navbar. Minor UX note
  (consider role-routing on login too), not a bug.

**Files altered:** added PNGs under `frontend/SCREENSHOTS/` (untracked). No source code
changed during verification.

---

## Session 3 — 2026-06-19 (Spec revision: NLP & image input — Phase 9 planning)

**Context / goal:** Feature owner revised `002-frontend-SPEC.md` AC-09/13/14/15 to require
NLP-prompt and image-based input. Plan the frontend delta before implementing (P1).

**Clarifications resolved (user):**
- **D5** — build NLP-prompt + image-upload UI; **mock** extraction/search behind
  `VITE_USE_MOCKS` (extends D3); real NLP/vision backend later.
- **D6** — vendor add/update: extraction **pre-fills the form for review then save**
  (keeps AC-05), not unattended "directly to inventory".
- **D7** — AC-15 delete stays a normal button + confirm action.
- **D8** — AC-09 search gains image upload → matched products, alongside text/NLP.

**Decisions / notes:**
- New assumed endpoints `POST /api/search/image` + `POST /api/extract/product`
  (`multipart/form-data`); `apiClient` to gain FormData support; mock derives fields
  heuristically (not real vision).
- ⚠️ **Image input is beyond master `SPEC.md`** (text + voice→text later) — logged in
  `architecture.md`, flagged for a human PR (P5; AI does not edit `SPEC.md`).

**Files altered (planning/audit only, no implementation yet):** updated
`specs/002-frontend/spec.md` (D5–D8, §5 AC's, §6 endpoints), `specs/002-frontend/plan.md`
(Phase 9 delta), appended `docs/architecture.md`.

**Approval state:** Phase 9 dry-run delta written; **awaiting user approval** before any
`frontend/` implementation file is created/modified (P1).

---

## Session 3 — 2026-06-19 (Phase 9 implementation: NLP & image input)

**Context / goal:** User approved the Phase 9 delta ("approve, implement Phase 9").
Implement AC-09 image search + AC-13/14 NLP/image extraction (prefill→save); AC-15
unchanged.

**Work done (`frontend/`):**
- `services/apiClient.js`: `FormData`/multipart support (skip JSON header; browser sets
  boundary); mock branch passes FormData through.
- `services/searchService.js`: `searchByImage(file)` → `POST /api/search/image`.
- `services/extractService.js` (new): `extractProduct({prompt,image})` →
  `POST /api/extract/product`.
- `services/_mocks/index.js`: FormData-aware `readBody`; `searchImage` (filename keyword
  → cheapest-first, fallback in-stock) and `extractProductFields` (heuristic
  price/stock/category/name parse; refined name cleanup to strip units + category word).
- `utils/constants.js`: `API_ROUTES.searchImage`, `API_ROUTES.extractProduct`.
- `components/products/ProductExtractPanel.jsx` (+css, new): prompt + image control.
- `pages/VendorPage.jsx`: embeds `ProductExtractPanel` in add/edit modal; `applyExtracted`
  pre-fills only returned fields, vendor reviews + saves (D6).
- `pages/SearchPage.jsx` (+`search.css`): image-upload row + `onImageSearch` (D8).
- Docs updated: `API_INTEGRATION_GUIDE`, `COMPONENT_DOCUMENTATION`, `TEST_CASES`, `README`.

**Verification (passed):**
- `npm run lint` clean; `npm run build` ok (98 modules, ~3s, JS ~86 kB gzip).
- **Browser (Edge via playwright-core), zero console/page errors:**
  - Image search (`tomato.png`) → 7 result cards rendered (AC-09). → `ImageSearch.png`
  - Vendor add via prompt "Amul butter 100g, ₹58, 30 in stock, Dairy" → form pre-filled
    `name="Amul butter" price=58 stock=30 category=Dairy`; saved → row added (AC-13).
    → `VendorExtract.png`

**Findings / notes:**
- Mock image search rarely keyword-matches a short filename, so it falls back to
  "visually similar" (all in-stock, cheapest-first). Acceptable for a mock; real matching
  is the backend's job (R5).
- Mock extraction is heuristic; vendor always reviews before saving (D6) so imperfect
  parses are corrected by a human.

**Files altered:** new `extractService.js`, `ProductExtractPanel.jsx`(+css); modified
`apiClient.js`, `searchService.js`, `_mocks/index.js`, `constants.js`, `VendorPage.jsx`,
`SearchPage.jsx`, `search.css`, and 4 docs. New screenshots `ImageSearch.png`,
`VendorExtract.png`. No other slice touched.

**Approval state:** **Phase 9 complete and browser-verified.** Outstanding (human):
(a) Docker image build on a host with a daemon; (b) PR to reconcile `SPEC.md` for React
19 (R1) and image input (R6); (c) swap mock NLP/vision for the real backend when ready.

---

## Session 4 — 2026-06-19 (Spec revision 2: voice input — Phase 10 planning)

**Context / goal:** Owner revised AC-09/11/13/14/15 again to add **voice** input, and
AC-11 chatbot to accept voice/text/image. Plan the delta before implementing (P1).

**Clarifications resolved (user):**
- **D9** — voice via **browser Web Speech API** (voice→text; mic hidden where unsupported).
  Aligns with master `SPEC.md` §2 ("voice→text later") — not a divergence.
- **D10** — chatbot adds mic + image attach; image → `POST /api/chat` (multipart) → reply
  + listings.
- **D11** — AC-15 delete: voice/text prompt names the product → match → existing confirm
  (supersedes D7).

**Decisions / notes:** reusable `useVoiceInput` + `VoiceButton` across search/chat/vendor;
chat gains multipart image; voice-delete matches client-side then confirms. Speech itself
isn't headlessly automatable → verified manually; text-equivalent paths automatable (R7).

**Files altered (planning/audit only):** `specs/002-frontend/spec.md` (D9–D11, §5/§6),
`specs/002-frontend/plan.md` (Phase 10 delta), appended `docs/architecture.md`.

**Approval state:** Phase 10 dry-run delta written; **awaiting user approval** before any
`frontend/` implementation file is created/modified (P1).

---

## Session 4 — 2026-06-19 (Phase 10 implementation: voice + chatbot media + voice delete)

**Context / goal:** User approved ("approve, implement Phase 10"). Implement voice input
(AC-09/11/13/14), chatbot image (AC-11), and voice/NLP delete (AC-15).

**Work done (`frontend/`):**
- `hooks/useVoiceInput.js` (new): Web Speech API wrapper (`supported/listening/toggle` +
  `onResult`); feature-detected, cleans up recognition on unmount.
- `components/common/VoiceButton.jsx` (+css, new): mic toggle; renders null when
  unsupported; pulse animation (reduced-motion aware).
- `pages/SearchPage.jsx`: VoiceButton → sets query + searches (AC-09).
- `components/chatbot/ChatInput.jsx`: rebuilt with mic + image attach + chip; emits
  `onSend(text, image)` (AC-11).
- `store/chatbotContext.jsx`: `sendMessage(text, image?)` (image shown as `📷 name`).
- `services/chatbotService.js`: `sendChat(message, sessionId, image?)` — multipart on image.
- `services/_mocks/index.js`: `chat()` FormData-aware; image → filename keyword + fallback.
- `components/products/ProductExtractPanel.jsx`: VoiceButton dictates into the prompt.
- `pages/VendorPage.jsx` (+`vendor.css`): "delete by description" input + mic →
  `findToDelete` matches the vendor's product → existing confirm modal (AC-15, D11).
- Docs updated: `API_INTEGRATION_GUIDE`, `COMPONENT_DOCUMENTATION`, `TEST_CASES`, `README`.

**Verification:**
- `npm run lint` clean; `npm run build` ok (101 modules, ~3.6s, JS ~87.5 kB gzip).
- **Browser (Edge/playwright), zero console/page errors:**
  - Voice mic **renders** on search, chat, and extract panel (Web Speech API detected).
  - Chat **image** attach → user bubble `📷 tomato.png`, bot reply + 2 listings (AC-11).
    → `ChatMedia.png`
  - **Delete-by-description** typed "remove the milk" → matched "Full Cream Milk 1L" →
    confirm → deleted (rows 2→1) (AC-15). → `VoiceDelete.png`
- ⚠️ **Actual speech recognition NOT verified** — Web Speech API needs a real mic and
  isn't automatable headlessly. The mic-renders + text-equivalent paths are verified;
  live dictation needs a manual browser test (marked 🎙️ in TEST_CASES).

**Findings / notes:** image keyword match worked here ("tomato.png" → Tomatoes); short
filenames may otherwise fall back to "visually similar" (mock limitation, R5). Voice is an
enhancement over the always-present text input (R7).

**Files altered:** new `useVoiceInput.js`, `VoiceButton.jsx`(+css); modified `SearchPage`,
`ChatInput`, `chatbotContext`, `chatbotService`, `_mocks/index.js`, `ProductExtractPanel`
(+css), `VendorPage`(+`vendor.css`), and 4 docs. New screenshots `ChatMedia.png`,
`VoiceDelete.png`. No other slice touched.

**Approval state:** **Phase 10 complete; automatable paths browser-verified.** Outstanding
(human): live mic/speech test; Docker image build (daemon); PR to reconcile `SPEC.md`
(React 19 R1, image input R6); swap mock NLP/vision for the real backend.
