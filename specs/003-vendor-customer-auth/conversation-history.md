# Conversation History — Feature 003: Vendor Customer Auth

Append-only, cumulative log of every working session on this feature
(Constitution P3 & P7). Earlier entries are NEVER overwritten or truncated.
Each entry: context/goal · decisions + reasoning · edge cases / unknowns ·
`[NEEDS CLARIFICATION]` raised or resolved · files altered.

---

## 2026-06-21 — Session 1: Feature scaffolding

- **Context / goal:** Initialise feature `003-vendor-customer-auth` via `/spec-create`.
- **Decisions:** Created `specs/003-vendor-customer-auth/` with `spec.md`, `plan.md`, `prompts.md`,
  `conversation-history.md`; set `.active_feature` → `003-vendor-customer-auth` (P7).
- **Unknowns raised:** spec.md & plan.md seeded with `[NEEDS CLARIFICATION]` markers
  to be resolved with the user before any implementation (P1, P2).
- **Files altered:** new feature folder + `.active_feature`.

---

## 2026-06-21 — Session 2: Spec & plan refinement

- **Context / goal:** Address 5 critical gaps: /me endpoint, signup flow (one vs two endpoints), vendor shop details timing, register rate limiting, refresh token rotation.
- **Decisions resolved:**
  - **GET /api/auth/me:** Added endpoint (FR-11) for frontend to fetch current user context (email, user_type, vendor_id/shop details if vendor).
  - **Two signup endpoints (FR-12):** POST `/auth/register` (customer) vs POST `/auth/register-vendor` (vendor + shop). Cleaner frontend logic, no role ambiguity.
  - **Shop details at signup (FR-13):** Vendors enter location (lat/lon) during registration, not post-onboarding. Simpler flow; can be edited later.
  - **Register rate limiting (FR-9b):** Max 10 registrations per IP per hour (in addition to login rate limiting).
  - **Refresh token rotation (FR-14, mandatory):** On each `/auth/refresh`, issue new refresh token + invalidate old one. Reduces exposure if token leaks.
- **Architectural changes:**
  - Added test file `backend/tests/test_auth_me.py`.
  - Updated `backend/app/routers/auth.py` to include GET /me handler.
  - Clarified location validation (±90 lat, ±180 lon) in plan.
  - Added R4 risk (refresh token storage race on network drop) + grace-period mitigation.
- **Unknowns remaining:** None; all `[NEEDS CLARIFICATION]` resolved (P2).
- **Files altered:** spec.md, plan.md, conversation-history.md.

---

## 2026-06-21 — Session 3: Phase 1 & 2 Implementation

**Phase 1: Database & Models (Complete)**
- Created migration `0003_add_email_password_auth.py` adding email, password_hash to users table
- Updated User, Vendor, RefreshToken models with email/password and location fields
- Models are pure SQLAlchemy (no business logic)

**Phase 2: Core Services (Complete)**
- Password service: bcrypt hashing, strength validation (min 8 chars, uppercase, digit, special char)
- JWT service: HS256 tokens, access (1h) + refresh (7d) with expiry validation
- Auth service: register_customer, register_vendor, login, refresh_access_token, logout, get_current_user
- Rate limiting service: in-memory counters for login (5 attempts/15 min) and signup (10/hour/IP)
- Comprehensive unit tests (test_password.py, test_jwt_service.py, test_rate_limit.py, test_auth_service.py)
- Dependencies added to pyproject.toml: python-jose, passlib, shapely, email-validator

**Phase 3: API Routes & Integration (Complete)**
- Pydantic schemas: RegisterRequest, RegisterVendorRequest, LoginRequest, RefreshRequest, AuthResponse, UserMeResponse
- FastAPI router with 6 endpoints:
  - POST `/register` → customer registration + JWT issuance
  - POST `/register-vendor` → vendor registration + shop location + JWT issuance
  - POST `/login` → authenticate, return access + refresh tokens
  - POST `/refresh` → rotate tokens (old refresh revoked)
  - POST `/logout` → revoke refresh token (idempotent)
  - GET `/me` → fetch current user (requires JWT in Authorization header)
- Rate limiting integrated: 429 on limit exceeded
- Location validation: ±90 lat, ±180 lon
- Password validation integrated: 400 on weak password
- Router wired into main.py at prefix=/api/auth
- .env.example updated with JWT_* and RATE_LIMIT_* placeholders

**Decisions:**
- Email validation via pydantic EmailStr
- Location in JSON request as {lat, lon}, stored as PostGIS POINT
- Token rotation on refresh: old refresh token immediately invalidated in DB
- Rate limits: separate counters per email (login) and per IP (signup)
- GET /me requires JWT in Authorization: Bearer <token> header

**Unknowns remaining:** None.
- **Files altered:** All Phase 1/2/3 files created; Phase 3: auth.py router, schemas/auth.py, main.py updated, pyproject.toml + .env.example updated.

---

## 2026-06-21 — Session 4: Phase 4 Comprehensive Testing

**Phase 4: Integration Tests (Complete)**
- test_auth_register.py: 13 tests
  - Happy path: customer + vendor registration
  - Validation: password strength, email format, mismatched passwords
  - Duplicate email rejection
  - Invalid location validation (lat ±90, lon ±180)
  - Rate limiting (10 signups/IP/hour)
  
- test_auth_login.py: 12 tests
  - Happy path: customer + vendor login
  - Invalid credentials (wrong password, nonexistent email)
  - Generic error message (no user enumeration)
  - Rate limiting (5 failures/email/15 min)
  - Counter cleared on successful login
  - Token structure validation (JWT format, different tokens)
  
- test_auth_refresh.py: 10 tests
  - Happy path: token refresh returns new tokens
  - Token rotation: old refresh token immediately revoked
  - Invalid token rejection (malformed, wrong type, empty)
  - Using access token as refresh token → 401
  - Multiple refreshes in sequence
  - Token claims preservation (user_id, user_type)
  
- test_auth_logout.py: 8 tests
  - Happy path: 204 response
  - Token revocation: refresh fails after logout
  - Idempotent: logout twice returns 204
  - Invalid token still succeeds (idempotency)
  - Multiple tokens: logout only revokes one
  - Complete flow: register → login → logout
  
- test_auth_me.py: 11 tests
  - Happy path: customer + vendor /me
  - Authorization header validation (missing, wrong prefix, invalid JWT)
  - Token type validation (refresh token rejected)
  - Customer vs vendor field differences
  - Consistent data across multiple requests
  - Refreshed token works for /me
  - Vendor details (location, description)

**Documentation:**
- docs/architecture.md: Added Feature 003 section with:
  - Complete auth flow diagram (ASCII)
  - 20 key architectural decisions (D12-D31)
  - Database schema
  - API contract table
  - Error handling matrix
  - Security measures & risk mitigations
  - Testing summary

**Test Coverage:**
- 54 total integration tests
- Covers: happy path, validation, rate limiting, token rotation, authorization, edge cases
- Uses FastAPI TestClient for end-to-end testing
- Fixtures: customer/vendor registration, login responses, access tokens

**Unknowns remaining:** None. All spec requirements covered.
- **Files altered:** test_auth_register.py, test_auth_login.py, test_auth_refresh.py, test_auth_logout.py, test_auth_me.py created; docs/architecture.md appended with Feature 003 decisions.
