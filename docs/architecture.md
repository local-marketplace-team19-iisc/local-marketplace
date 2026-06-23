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
  `frontend/FRONTEND_DOCUMENTATION.md` §4. When the backend publishes real endpoints, flip
  the toggle/base URL — no UI changes required.
- **Build tooling — Vite** (React 19; CRA deprecated). Consequence: `index.html` lives
  at the `frontend/` root (Vite convention), deviating from the input spec's
  `public/index.html` drawing. `public/` holds static assets.
- **Auth/token handling — JWT in memory only** (Constitution-aligned with C-09: no
  sensitive data in browser storage). Session is lost on refresh; the production target
  is an httpOnly cookie issued by the backend, deferred to the auth/backend feature.

Open items (tracked in `specs/002-frontend/spec.md` §7): backend endpoint confirmation,
optional UI component library, and whether `TEST_CASES` must be a true `.xlsx`.

### Feature 002 — Frontend: NLP & image input (spec revision 2026-06-19)

The feature owner updated AC-09/13/14/15 to require NLP-prompt and image-based input.
Decisions:

- **D5 — NLP/image via mocked extraction.** Frontend adds NLP-prompt + image-upload UI;
  extraction/search is mocked behind `VITE_USE_MOCKS` (extends D3). New assumed endpoints:
  `POST /api/search/image` and `POST /api/extract/product` (both `multipart/form-data`).
  The mock derives fields heuristically from prompt text / image filename — **not real
  vision** — for flow demonstration; real NLP/vision wired later by flipping the toggle.
- **D6 — Vendor add/update flow:** extraction **pre-fills the form for review then save**
  (keeps AC-05 validation), rather than writing "directly to inventory" unattended.
- **D7 — Delete (AC-15)** stays a normal button + confirmation action.
- **D8 — Customer search (AC-09)** gains image upload → matched products, alongside the
  existing text/NLP query.
- ⚠️ **Image input is beyond master `SPEC.md`** (text + voice→text later; no images).
  Recorded here as a divergence; **requires a human PR** to update `SPEC.md` (AI does not
  edit it, P5).

### Feature 002 — Frontend: Voice input + chatbot media + voice delete (spec revision 2026-06-19b)

AC-09/11/13/14/15 revised again to add voice input; AC-11 chatbot to accept voice/text/image.

- **D9 — Voice via browser Web Speech API** (`SpeechRecognition`/`webkitSpeechRecognition`).
  Reusable `useVoiceInput` hook + `VoiceButton`, reused in search, chatbot, vendor extract,
  and voice-delete. Voice→text only (transcription client-side); the resulting text flows
  through existing text endpoints. Mic hidden/disabled where unsupported (Firefox, older
  Safari) — graceful degradation for AC-06. **Aligns with master `SPEC.md` §2** ("voice→text
  later") — not a divergence (unlike image).
- **D10 — Chatbot media:** chat input adds mic + image attach; image sent to `POST /api/chat`
  (multipart) → reply + listings (mock derives from filename).
- **D11 — Voice/NLP delete (AC-15):** a voice/text prompt names the product; the frontend
  matches it among the vendor's own products and opens the existing delete confirmation.
  Supersedes D7 ("normal delete only"); confirmation retained for safety.
- Browser-automation note: Web Speech API needs a real mic + can't run in headless
  automation, so speech itself is verified manually; the text-equivalent paths (typed
  prompt, image attach, typed delete prompt) and the mic's supported/disabled gating are
  automatable.

---

## Feature 003 — Vendor & Customer Email/Password Authentication (2026-06-21)

Email/password authentication with JWT tokens. Customers and vendors register separately;
vendors provide shop location at signup. Tokens stored in memory (no localStorage).

### Key Decisions

- **D12 — Two signup endpoints (not role selector):** `POST /auth/register` (customer-only)
  and `POST /auth/register-vendor` (vendor + shop). Avoids role-selection UI confusion in
  frontend; each endpoint explicitly expects the right payload (shop_name/location for
  vendor). Aligns with C-12 (customer/vendor distinct flows).

- **D13 — Shop location at registration, not post-onboarding:** Vendors enter location
  (lat/lon) during signup as a required field. Simpler flow; location can be updated later
  via PATCH (future). Enables geospatial indexing in Phase 004.

- **D14 — JWT token rotation on refresh:** Each call to `POST /auth/refresh` issues a
  new refresh token and immediately revokes the old one in the DB. Reduces exposure if a
  token leaks; client must update in-memory token. Mandatory (not optional) for security.

- **D15 — Rate limiting (in-memory Phase 2):** Login: 5 failed per email per 15 min → 429.
  Signup: 10 per IP per hour → 429. In-memory counters (adequate for single-instance);
  upgrade to Redis (Phase 2b) for multi-instance deployments.

- **D16 — Token storage (adheres to C-09):** Access tokens (1h) and refresh tokens (7d)
  stored in memory only; frontend never writes to localStorage/sessionStorage. On page
  refresh, frontend calls `GET /auth/me` to restore user context (requires valid in-memory
  token, or user must re-login). Production: deploy with httpOnly refresh cookies (future
  Phase 3b, if needed).

- **D17 — Generic login error:** Both wrong password and nonexistent email return 401 with
  identical "Invalid credentials" message. Prevents user enumeration attacks (C-08).

- **D18 — Two user tables (users + vendors):** Not a single polymorphic table. Users table
  holds email, password, role enum. Vendors table: user_id FK (1:1), shop fields, PostGIS
  location. Cleaner schema; JOIN on queries is negligible at this scale.

- **D19 — PostGIS for location:** Shop location stored as POINT(lon, lat) with SRID 4326
  (WGS84). Enables geo-queries and spatial indexing (Phase 004+). Validation: ±90 lat,
  ±180 lon at registration. Client sends {lat, lon}; backend converts to (lon, lat) for
  PostGIS (standard order).

- **D20 — Refresh token hash in DB:** Refresh token JWT is hashed (SHA256) before storage.
  Reduces exposure if DB is leaked; actual JWT never stored plaintext. On refresh call,
  client sends the full JWT; backend hashes it and looks up the record.

### API Contracts

6 endpoints under `/api/auth/`:

- `POST /register` → Customer signup (email, password, password_confirm)
  - Response: 201, {access_token, refresh_token, user_id, user_type="customer"}
  - Errors: 400 (validation/duplicate), 429 (rate limit)

- `POST /register-vendor` → Vendor signup (email, password, shop_name, location {lat,lon}, description?)
  - Response: 201, {access_token, refresh_token, user_id, vendor_id, user_type="vendor", shop_name}
  - Errors: 400 (validation/duplicate/invalid location), 429 (rate limit)

- `POST /login` → Authenticate (email, password)
  - Response: 200, {access_token, refresh_token, user_id, user_type}
  - Errors: 401 (invalid creds), 429 (rate limit)

- `POST /refresh` → Rotate tokens (refresh_token)
  - Response: 200, {access_token, refresh_token, user_id, user_type}
  - Errors: 401 (invalid/expired/revoked)
  - Side effect: old refresh_token marked revoked in DB

- `POST /logout` → Revoke refresh token (refresh_token)
  - Response: 204 (no content)
  - Idempotent: 204 even if token already revoked
  - Side effect: refresh_token.revoked_at = now()

- `GET /me` → Current user profile (requires `Authorization: Bearer <access_token>`)
  - Response: 200, {id, email, user_type, vendor_id?, shop_name?, shop_description?, shop_location?}
  - Errors: 401 (missing/invalid JWT)
  - Vendor fields only included if user_type="vendor"

### Database Changes

Migration `0003_add_email_password_auth.py`:
- users: +email (UNIQUE, indexed), +password_hash
- vendors: +shop_description, +is_active
- refresh_tokens: revoked → revoked_at (DATETIME, nullable, indexed)

### Testing

Integration tests cover all endpoints:
- Happy path: register/login/refresh/logout/me
- Validation: weak password, invalid email, duplicate email, invalid location
- Rate limiting: 429 on limit exceeded, clear on successful login
- Token rotation: old token rejected after refresh
- Auth errors: 401 on invalid/expired/missing tokens
- Edge cases: idempotent logout, refresh with wrong token, /me with refresh token (rejected)

---

## Feature 006 — Vendor Product Management (2026-06-23)

Persists the Feature 005 catalog and adds the vendor create/delete-by-description
workflow. `backend/app/catalog/` (+ new models/services/routes) and the
`frontend/` vendor slice. Decisions:

- **D1 — Runtime database is PostgreSQL.** New tables (`categories`,
  `subcategories`, `products`) are created by Alembic `0004` (down_revision
  `0003`), consistent with the existing Postgres-only chain (postgis/geoalchemy2).
  No `create_all` runs in app startup. (User decision, 2026-06-23.)
- **D2 — ID convention preserved, not "fixed".** ORM models declare `String(36)`
  ids while migrations emit PostgreSQL `UUID` — exactly as the existing
  `users`/`vendors` models/migrations. 006 follows this rather than touching
  003-owned files.
- **D3 — `products` adds the four operational fields 005 deferred** (005 FR-14/15):
  `vendor_id` (FK→vendors), `stock_quantity`, `created_at`, `updated_at`. 005 §4
  remains the schema authority for the catalog fields.
- **D4 — Unknown category → seeded `General → General` subcategory**, keeping 005
  `subcategory_id` NOT NULL (005 FR-6). Taxonomy is seeded from the 005 examples
  + frontend `PRODUCT_CATEGORIES`, single-sourced in `catalog/seed_data.py`.
- **D5 — Deterministic (non-LLM) parser** (`catalog/parser.py`): extracts
  name/brand/price/unit/stock/category. Defaults brand `"Generic"`, `PIECE`/`1`,
  stock `0`; a **missing price is rejected** (005 FR-16 — price is mandatory).
- **D6 — REST normalizes price to 2 dp** rather than rejecting under-precise input
  (the strict "reject 10.1" rule is a 005 model-layer rule; the vendor API
  normalizes — same stored result, friendlier UX).
- **D7 — Writes are vendor-scoped via the 003 JWT** (`Bearer`); reads
  (`GET /api/products`, `/api/catalog/*`) are public. `delete-by-description`
  scores only the caller's own rows and deletes the best match (404 if none).
- **D8 — `GET /api/products` returns display aliases + raw catalog fields** so the
  existing `VendorPage` renders unchanged (name↔product_name, price↔price_inr,
  stock↔stock_quantity, category↔(sub)category name, vendorId↔vendor_id).
- **D9 — Swagger enabled** (`docs_url="/docs"`, `openapi_url="/openapi.json"`) per
  the feature request / acceptance criteria.
  - ⚠️ **Conflict with SPEC §7 / `backend/tests/test_health.py::test_no_route_other_than_health`**,
    which asserts auto-docs are disabled. The explicit feature requirement to
    enable Swagger supersedes for this feature; reconciling SPEC §7 and the 000
    scaffold test requires a human decision (Constitution P5 — AI must not edit
    `SPEC.md`). Recorded here; the 000 test is intentionally left untouched pending
    that decision.
- **D10 — Tests run on in-memory SQLite** (portable ORM column types) for speed,
  even though runtime is Postgres.

**Environment note (not a 006 defect).** A fresh dependency install resolves
`bcrypt` to 5.0.0, which is incompatible with the pinned `passlib==1.7.4`
(`ValueError: password cannot be longer than 72 bytes`), causing the pre-existing
auth/password tests (003) to error. 006's own tests are green. Pinning
`bcrypt<4.1` would restore the auth suite but touches 003/governance config —
  left for a human decision.

### Feature 006 — post-merge ORM model fix-up (2026-06-23)

The PR landed without `backend/app/models/{category,product,subcategory}.py`,
so `services/product_service.py` was un-importable on `main`. These three
ORM files were added in the 008-cleanup session to match the Alembic 0004
schema (portable SQLAlchemy column types: `Uuid(as_uuid=True)`, `String(20)`
for `unit_type` so the same models run on SQLite for tests/local dev and
on Postgres in production). Logged in
`specs/008-sbert-intent-router/conversation-history.md` (Session 3).

---

## Feature 008 — SBERT Lightweight Intent Router (2026-06-23)

V1 of the natural-language agent. Replaces the planner/orchestrator/tool-registry
design from feature 002/007 with a stateless, LLM-free pipeline:

```
text → SBERT classify → role gate → regex/SBERT extract → existing API → projection → wire
```

### Key decisions

- **D-008-1 — No LLM in the request path.** Feature 002's planner code stays
  on disk (rollback path), but `/api/chat`, `/api/agent/route`, and `/api/search`
  all go through `backend.app.agent_router.route.route_text(...)` instead. No
  network calls outside the optional one-time SBERT download.
- **D-008-2 — Six labelled intents + `unknown`** (spec FR-1):
  `search_products`, `add_product`, `update_product`, `delete_product`,
  `get_my_listings`, `get_categories`. The classifier returns `unknown` when
  the best prototype cosine similarity is below
  `INTENT_CONFIDENCE_THRESHOLD` (default 0.45).
- **D-008-3 — SBERT model: `all-MiniLM-L6-v2`** (80 MB, English, CPU-friendly).
  Multilingual variants are deferred to v1.x; the model id is one
  config-key swap away.
- **D-008-4 — Entity extraction is deterministic.** Regex covers price,
  max/min price, product id. SBERT is only used for the fuzzy category-name
  match. The router never asks an LLM to extract structured data from text.
- **D-008-5 — Stateless.** No Redis, no session memory. The chat endpoint
  echoes a synthetic `sessionId` back so the frontend's existing UI
  contract doesn't break.
- **D-008-6 — Products API is the real feature 006.** As of the
  2026-06-23 cleanup session, the temporary `products_stub/` is gone.
  The SBERT router dispatches into `backend.app.services.product_service`
  (006) directly, using a sync `Session` from `db.session.SessionLocal`.
  When the deferred 001 catalog migration lands, no router changes are
  needed.

### HTTP surfaces

| Endpoint | Auth | Shape |
|---|---|---|
| `POST /api/agent/route` | Bearer required | Verbose: `{intent, entities, reply, listings, api_called, api_status, meta}` |
| `POST /api/chat` | Bearer required | Frontend-compatible: `{reply, listings, sessionId}` |
| `GET /api/search?q=...` | Bearer optional | Listings-only: `{products, meta}` |

### Testing

- `make router-test` runs the agent-router fast suite (SBERT loader
  cache/snapshot/download branches, deterministic entity extraction,
  router dispatch per intent with classifier mocked, cross-vendor
  protection, endpoint-level adapters, timeout fall-through).
- 1 slow test (`make sbert-test`, opt-in via `-m slow`) — loads the real
  SBERT model and asserts ≥ 90 % accuracy on a 35-case labelled set
  including 5 distractors that MUST resolve to `unknown`.

### Operational

- `make sbert-download` pre-fetches the model into `MODELS_DIR`
  (default `./models/sbert`). After that, the app boots offline.
- `ALLOW_MODEL_DOWNLOAD=false` (the default) makes the loader fail fast
  with a friendly "MODELS_DIR / ALLOW_MODEL_DOWNLOAD" message rather than
  hanging on the first request when neither is set.

---

### Feature 000 — App Scaffold (logged retroactively)

The runnable starting point: FastAPI + uvicorn, `/health`, ruff, pytest,
`.env.example`. Governed like a feature but not a product feature; its
`spec.md` is the master `SPEC.md`.

- **D-000-1 — FastAPI on Python 3.11.** Async-capable, OpenAPI by
  convention, matches SPEC §5.
- **D-000-2 — `pydantic-settings` for config.** Single `Settings` class
  reads from env + `.env`; `.env.example` committed, `.env` gitignored
  (Constitution P4).
- **D-000-3 — `ruff` is the only linter/formatter.** No `black` /
  `flake8` / `isort` to avoid tool drift.
- **D-000-4 — `pytest + httpx` for the test harness.** TestClient is
  the contract surface for every later feature's HTTP tests.

### Feature 001 — DB Schema (logged retroactively)

The ORM and migrations baseline that every later feature depends on.

- **D-001-1 — SQLAlchemy 2.x `DeclarativeBase`** in `models/base.py`;
  every model in `models/models.py` (single-file is intentional for V1
  — split when it exceeds ~500 lines).
- **D-001-2 — Alembic for versioned migrations.** Migration files live
  in `backend/db/migrations/`; `down_revision` chain is the truth.
- **D-001-3 — Portable column types.** ORM uses `Uuid(as_uuid=True)`
  and short `String(...)` enums so the same models run on SQLite
  (tests, V1 local dev) and Postgres (production).
- **D-001-4 — PostGIS + pgvector planned, not yet enabled.** The
  schema reserves the location/embedding fields; extension creation is
  deferred to the feature that first needs the index.
- **D-001-5 — `db/init/01-extensions.sql`** is the one-time Docker
  bootstrap (`CREATE EXTENSION postgis, vector`) — runs from the
  Postgres container's `docker-entrypoint-initdb.d/`, not from app
  startup.

### Feature 005 — Catalog Taxonomy (logged retroactively)

Two-level catalog (category → subcategory) that 006 persists and 008
matches against. Decisions referenced by D4 of feature 006 and the
`category` extractor in feature 008.

- **D-005-1 — Two-level taxonomy.** `categories` and `subcategories`
  only — no n-ary tree. Keeps the parser, the dashboard form, and the
  SBERT category-match cosine all simple.
- **D-005-2 — Seed data is the source of truth.** `catalog/seed_data.py`
  declares the taxonomy in code; the seed runs idempotently at
  bootstrap. Frontend `PRODUCT_CATEGORIES` mirrors the same list.
- **D-005-3 — `subcategory_id` is NOT NULL on products** (FR-6).
  Unknown / free-form categories fall back to the seeded
  `General → General` subcategory (consumed by 006 D4).
- **D-005-4 — Price stored as `NUMERIC(12, 2)`** (₹, two decimal
  places per SPEC §2). 005 model layer rejects under-precision; the
  006 REST layer normalizes for friendlier UX (006 D6).

### Feature 004 — Frontend (logged retroactively, slug correction)

The React 19 SPA — customer chatbot, vendor dashboard, search bar,
text + voice→text input. This entry exists because the early
architectural decisions for this feature were appended to this log
under the heading **"Feature 002 — Frontend"** before slot 002 was
later reassigned to the parked planner/orchestrator agent (see Errata
below). The decisions themselves (D1–D11 above) remain valid — only
the heading is misleading.

Decisions added by later sessions that belong to feature 004:

- **D-004-12 — SBERT debug badge.** When `/api/chat` returns a
  `debug.intent` / `debug.confidence`, the chatbot bubble renders a
  small monospace badge showing both. Opt-in for developer surfaces;
  invisible to end users when the field is absent.
- **D-004-13 — Voice auto-submit UX.** The voice button auto-submits
  the transcript when the textarea is empty; appends otherwise.
  Implemented behind a single-shot `useRef` guard so React 18
  StrictMode's double-invocation of state updaters cannot fire two
  POSTs (feature 008 Session 9 / 10).
- **D-004-14 — `forced_intent` hint on `/api/chat`.** Specific UI
  flows (Add-Product modal) pass `intent: "add_product"` to the
  backend so SBERT classification is bypassed and a bare product
  description cannot be silently mis-classified.
- **D-004-15 — Tolerate two backend response shapes.** Search and
  product readers accept both `{products: [...]}` (new 006/008 shape)
  and `{results: [...]}` (legacy mock shape) without if/else trees in
  components.
- **D-004-17 — Per-identity provider isolation.** `ProductProvider`
  and `ChatbotProvider` now sit inside a keyed subtree rooted on
  `user?.id ?? 'guest'`. When the signed-in user changes (logout,
  login as a different user, or a session restore that resolves to a
  different account) React unmounts the old subtree and mounts a
  fresh one, giving every in-memory store (chat transcript, chatbot
  `sessionId`, cart, favorites, orders, search results) a clean
  slate without per-reducer reset plumbing. `AuthProvider` sits
  outside this boundary so its rehydrate effect (D-004-16) is not
  disturbed. This closes a session-leak bug where a customer's chat
  history (and cart) were still visible after switching to a vendor
  account in the same tab.
- **D-004-16 — JWT survives reload via `sessionStorage` (revises D16
  for dev, pragmatic refinement).** D16 originally specified
  "in-memory only" with restore via `GET /auth/me`. In practice that
  meant every manual refresh and every Vite HMR module replacement
  signed the user out, which surfaced as `401 Unauthorized` on
  `/api/orders` (and would have happened on any protected route).
  Revision: `AuthProvider` now caches `{token, user}` under the
  `lm:auth` key in `sessionStorage` (per-tab, wiped on tab close —
  closer to "in-memory" than `localStorage` and explicitly **not**
  the long-lived storage forbidden by Constitution C-09). On mount
  it reads the cache, pushes the token into `apiClient`, and calls
  `GET /auth/me` to verify it server-side; a 401 silently clears the
  cache. `ProtectedRoute` renders a "Restoring your session…"
  placeholder while `status === 'loading'` so a refresh on a guarded
  route does not flicker through `/login`. The eventual production
  target remains an httpOnly refresh cookie issued by the backend;
  this is a transitional measure until that lands.

---
