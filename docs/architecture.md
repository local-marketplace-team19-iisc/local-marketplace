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
