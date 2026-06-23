# Plan — Feature 003: Vendor Customer Auth (Dry-Run)

> **Iron-Clad Rule (Constitution P1 / SPEC §8):** this dry-run MUST be reviewed and
> **approved by the user** before any implementation file is created or modified.

## Implementation Phases

Build incrementally with clear exit criteria for each phase. Each phase is complete & testable before the next begins.

### Phase 1: Database & Models (Stub)
**Goal:** Set up schema and model definitions. No business logic yet.

**Deliverables:**
- `backend/migrations/001_create_auth_tables.py` — Alembic migration creating users, vendors, refresh_tokens tables with all columns, constraints, indexes
- `backend/app/models/user.py` — SQLAlchemy User model (id, email, password_hash, user_type, created_at, updated_at)
- `backend/app/models/vendor.py` — SQLAlchemy Vendor model (id, user_id, shop_name, location, shop_description, is_active, timestamps)
- `backend/app/models/refresh_token.py` — SQLAlchemy RefreshToken model (id, user_id, token_hash, expires_at, revoked_at, created_at)
- `backend/app/models/__init__.py` — Export all three models

**Success Criteria:**
- [ ] Migration runs: `alembic upgrade head` works without errors
- [ ] `psql -c "\dt"` shows users, vendors, refresh_tokens with correct columns
- [ ] Models import successfully: `from app.models import User, Vendor, RefreshToken`
- [ ] No business logic in models; they are pure SQLAlchemy definitions
- [ ] Relationships are defined: User ↔ Vendor (1:1), User ↔ RefreshToken (1:N)

**Out of scope this phase:** Hashing, JWT, API routes, validation

---

### Phase 2: Core Services (Business Logic)
**Goal:** Implement all auth logic in service layer. Testable independently, no HTTP yet.

**Deliverables:**
- `backend/app/security/password.py` — Password utilities:
  - `hash_password(password: str) -> str` — bcrypt hash
  - `verify_password(plain: str, hashed: str) -> bool` — bcrypt verify
  - `validate_password_strength(password: str) -> tuple[bool, str]` — min 8 chars, uppercase, digit, special char
- `backend/app/services/jwt_service.py` — JWT logic:
  - `create_access_token(user_id: UUID, user_type: str, expires_delta: timedelta) -> str` — HS256 token with claims (user_id, user_type, exp)
  - `create_refresh_token(user_id: UUID) -> str` — Separate refresh token (longer TTL)
  - `verify_token(token: str) -> dict` — Decode & validate, raise on expired/invalid
  - `verify_refresh_token(token: str, token_hash_from_db: str) -> bool` — Verify refresh token matches DB hash
- `backend/app/services/auth_service.py` — Auth business logic:
  - `register_customer(email: str, password: str) -> dict` — Create user, return {user_id, email, user_type}
  - `register_vendor(email: str, password: str, shop_name: str, location: tuple[float, float], shop_description: str) -> dict` — Create user + vendor in transaction, return {user_id, vendor_id, user_type}
  - `login(email: str, password: str) -> dict` — Validate, return {user_id, user_type, access_token, refresh_token}
  - `refresh_access_token(old_refresh_token: str, user_id: UUID) -> dict` — Validate refresh token, issue new access + refresh tokens, revoke old refresh token
  - `logout(user_id: UUID, refresh_token: str) -> bool` — Mark refresh token as revoked
  - `get_current_user(access_token: str) -> dict` — Decode token, fetch user from DB, return {id, email, user_type, vendor_id, shop_name, location}
- `backend/app/services/rate_limit.py` — Rate limiting (in-memory, Phase 2):
  - `check_login_rate_limit(email: str) -> tuple[bool, str]` — Max 5 failed in 15 min, return (allowed, reason)
  - `check_signup_rate_limit(ip: str) -> tuple[bool, str]` — Max 10 per hour, return (allowed, reason)
  - `record_failed_login(email: str) -> None` — Increment counter
  - `clear_failed_login(email: str) -> None` — Reset on successful login
- `backend/tests/conftest.py` — Pytest fixtures:
  - `test_db()` — In-memory SQLite for testing
  - `test_client` — FastAPI TestClient (added later, but fixture defined now)
  - `sample_user_payload()` — Dict with {email, password, user_type}
  - `sample_vendor_payload()` — Dict with {email, password, shop_name, location, shop_description}
- Unit tests (Phase 2 candidate; see Phase 4):
  - `backend/tests/test_password.py` — hash_password, verify_password, validate_password_strength
  - `backend/tests/test_jwt_service.py` — create_access_token, create_refresh_token, verify_token
  - `backend/tests/test_auth_service.py` — register_customer, register_vendor, login, refresh, logout, get_current_user

**Success Criteria:**
- [ ] All service functions are importable and callable
- [ ] `make test` runs all unit tests in test_password.py, test_jwt_service.py, test_auth_service.py with 100% pass
- [ ] Password strength validation rejects weak passwords, accepts strong ones
- [ ] JWT tokens encode/decode correctly; expired tokens raise; invalid tokens raise
- [ ] register_customer creates user in DB; register_vendor creates user + vendor in transaction
- [ ] login validates email/password, returns tokens
- [ ] refresh_access_token issues new tokens, invalidates old refresh token
- [ ] logout marks refresh token as revoked; get_current_user returns correct user info
- [ ] Rate limit functions return correct allow/deny decisions
- [ ] No HTTP/API code; services are DB + business logic only

**Out of scope this phase:** Pydantic schemas, FastAPI routes, HTTP responses

---

### Phase 3: API Routes & Integration with Main
**Goal:** Expose services via FastAPI endpoints. Wire into app.main.

**Deliverables:**
- `backend/app/schemas/auth.py` — Pydantic request/response schemas:
  - `RegisterRequest` — {email, password, password_confirm}
  - `RegisterVendorRequest` — {email, password, password_confirm, shop_name, location: {lat, lon}, shop_description}
  - `LoginRequest` — {email, password}
  - `RefreshRequest` — {refresh_token}
  - `AuthResponse` — {access_token, refresh_token, user_id, user_type} (returned from register/login/refresh)
  - `UserMeResponse` — {id, email, user_type, vendor_id?, shop_name?, shop_location?}
- `backend/app/routers/auth.py` — FastAPI endpoints:
  - `POST /register` — Call auth_service.register_customer, return 201 + AuthResponse; 400 on validation/duplicate email; 429 on rate limit
  - `POST /register-vendor` — Call auth_service.register_vendor, return 201 + AuthResponse; 400 on validation/invalid location; 429 on rate limit
  - `POST /login` — Call auth_service.login, return 200 + AuthResponse; 401 on wrong credentials; 429 on rate limit
  - `POST /refresh` — Call auth_service.refresh_access_token, return 200 + new tokens; 401 on invalid/expired refresh token
  - `POST /logout` — Call auth_service.logout, return 204 No Content; 401 if not authenticated
  - `GET /me` — Call auth_service.get_current_user, return 200 + UserMeResponse; 401 if not authenticated
- `backend/app/main.py` — Wire auth router:
  - `app.include_router(auth.router, prefix="/api/auth", tags=["auth"])`
- `backend/.env.example` — Add auth env vars (if not present, merge only):
  - `JWT_SECRET=your-secret-here`
  - `JWT_ACCESS_TOKEN_TTL_MINUTES=60`
  - `JWT_REFRESH_TOKEN_TTL_DAYS=7`
  - `RATE_LIMIT_FAILED_LOGIN_ATTEMPTS=5`
  - `RATE_LIMIT_LOCKOUT_MINUTES=15`
  - `RATE_LIMIT_SIGNUP_PER_IP_HOUR=10`
- `backend/pyproject.toml` — Add dependencies (idempotent):
  - `python-jose[cryptography]` (for JWT)
  - `passlib[bcrypt]` (for password hashing)
  - `slowapi` (optional, for advanced rate limiting; Phase 2 uses simple in-memory)

**Success Criteria:**
- [ ] All endpoints respond with correct HTTP status codes
- [ ] POST /register creates a customer user, returns 201 + AuthResponse with user_type='customer'
- [ ] POST /register-vendor creates vendor user, returns 201 + AuthResponse with user_type='vendor'
- [ ] POST /login returns 200 + tokens on valid credentials; 401 on invalid
- [ ] POST /refresh returns 200 + new tokens (old refresh token invalidated in DB)
- [ ] POST /logout returns 204; subsequent refresh with revoked token returns 401
- [ ] GET /me returns 200 + UserMeResponse with user_type and vendor fields (if vendor); 401 without JWT
- [ ] Rate limit responses (429) are returned correctly on limit exceeded
- [ ] Endpoints are accessible at `/api/auth/<endpoint>`
- [ ] Request/response validation works: 400 on invalid schema, descriptive error messages
- [ ] `make lint` passes (no import errors, style clean)

**Out of scope this phase:** End-to-end frontend testing, comprehensive edge case coverage

---

### Phase 4: Comprehensive Testing & Refinement
**Goal:** Integration tests, edge cases, full acceptance criteria verification.

**Deliverables:**
- `backend/tests/test_auth_register.py` — Registration integration tests:
  - Test POST /register with valid customer data → 201, user created
  - Test POST /register-vendor with valid vendor data → 201, user + vendor created
  - Test POST /register-vendor with invalid location (>90 lat) → 400
  - Test duplicate email on both endpoints → 400 "Email already registered"
  - Test weak password → 400 "Password must contain..."
  - Test rate limit (10+ signups from same IP in 1 hour) → 429
- `backend/tests/test_auth_login.py` — Login integration tests:
  - Test POST /login with correct credentials → 200, JWT tokens returned
  - Test POST /login with wrong password → 401 "Invalid credentials"
  - Test POST /login with nonexistent email → 401 "Invalid credentials"
  - Test rate limit (5+ failed attempts in 15 min) → 429
  - Test lockout expires after 15 min
- `backend/tests/test_auth_refresh.py` — Token refresh integration tests:
  - Test POST /refresh with valid refresh token → 200, new access token + new refresh token issued
  - Test POST /refresh with old refresh token after rotation → 401 (old token revoked)
  - Test POST /refresh with expired refresh token → 401
  - Test POST /refresh with invalid token format → 401
- `backend/tests/test_auth_logout.py` — Logout integration tests:
  - Test POST /logout with valid JWT → 204
  - Test POST /logout, then POST /refresh with same refresh token → 401 (revoked)
  - Test POST /logout twice → 204 (idempotent)
- `backend/tests/test_auth_me.py` — GET /me integration tests:
  - Test GET /me with valid customer JWT → 200, return customer data
  - Test GET /me with valid vendor JWT → 200, return vendor data including shop_name, location, vendor_id
  - Test GET /me without JWT → 401
  - Test GET /me with expired JWT → 401
- Manual / End-to-End tests (documented in Verification section):
  - Register customer → login → get /me → refresh token → logout
  - Register vendor with location → login → get /me (check vendor fields) → refresh → logout
  - Rate limit signup (10+), rate limit login (5+)
  - Token expiry & refresh before expiry

**Success Criteria:**
- [ ] `make test` runs all test files: test_password.py, test_jwt_service.py, test_auth_service.py, test_auth_register.py, test_auth_login.py, test_auth_refresh.py, test_auth_logout.py, test_auth_me.py
- [ ] All tests pass (100% pass rate)
- [ ] Code coverage ≥80% for auth module (services, routers)
- [ ] All acceptance criteria from spec.md §3 are verified by tests
- [ ] Manual verification (see Verification section) completes successfully
- [ ] `make lint` passes, `ruff check .` clean
- [ ] `docs/architecture.md` updated with auth flow diagram/description

**Exit Criteria for Feature Completion:**
- [ ] Phase 1, 2, 3, 4 all complete
- [ ] All tests pass
- [ ] All spec requirements (FR-1 through FR-14) verified
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Feature committed to branch 003-vendor-customer-auth
- [ ] PR opened (linked to spec.md)

---

## Scope

**Delivers:**
- Email/password registration & login for customers & vendors
- JWT access + refresh token generation, validation, refresh, revocation
- Vendor onboarding with shop location (lat/lon)
- Rate limiting on failed login attempts
- Backend API endpoints: `/auth/register`, `/auth/register-vendor`, `/auth/login`, `/auth/refresh`, `/auth/logout`
- DB migrations for users, vendors, refresh_tokens tables
- Password hashing (bcrypt) & validation

**Out of scope:**
- Email verification / confirmation (future feature)
- OAuth / social login
- MFA / OTP
- Password reset flow (future)
- Admin user management UI
- Frontend implementation (Feature 002 already has email/password form)

## Files to CREATE

| Path | Purpose |
| :-- | :-- |
| `backend/app/models/user.py` | SQLAlchemy User model (id, email, password_hash, user_type, timestamps) |
| `backend/app/models/vendor.py` | SQLAlchemy Vendor model (id, user_id, shop_name, location, shop_description, is_active) |
| `backend/app/models/refresh_token.py` | SQLAlchemy RefreshToken model (id, user_id, token_hash, expires_at, revoked_at) |
| `backend/app/schemas/auth.py` | Pydantic schemas: RegisterRequest, RegisterVendorRequest, LoginRequest, AuthResponse (access_token, refresh_token, user_id, user_type) |
| `backend/app/routers/auth.py` | FastAPI endpoints: POST /register, /register-vendor, /login, /refresh, /logout; GET /me |
| `backend/app/services/auth_service.py` | Business logic: hash_password, verify_password, create_jwt, verify_jwt, refresh_token logic, rate limiting |
| `backend/app/services/jwt_service.py` | JWT creation/verification (HS256, claim validation) |
| `backend/app/security/password.py` | Password hashing (bcrypt) and validation utilities |
| `backend/migrations/001_create_users_vendors.py` | Alembic migration: create users, vendors, refresh_tokens tables |
| `backend/tests/test_auth_register.py` | Unit tests: register customer, register vendor, edge cases (duplicate email, weak password, etc.) |
| `backend/tests/test_auth_login.py` | Unit tests: login, rate limiting, invalid credentials |
| `backend/tests/test_auth_refresh.py` | Unit tests: token refresh, expired tokens, revoked tokens |
| `backend/tests/test_auth_logout.py` | Unit tests: logout, token revocation |
| `backend/tests/test_auth_me.py` | Unit tests: GET /me with valid/invalid JWT, customer vs vendor payloads |

## Files to MODIFY (append/merge only — Constitution P6)

| Path | Change |
| :-- | :-- |
| `backend/app/main.py` | Add router: `app.include_router(auth.router, prefix="/api/auth", tags=["auth"])` |
| `backend/app/models/__init__.py` | Export User, Vendor, RefreshToken models |
| `backend/.env.example` | Add env vars: `JWT_SECRET`, `JWT_ACCESS_TOKEN_TTL_MINUTES=60`, `JWT_REFRESH_TOKEN_TTL_DAYS=7`, `RATE_LIMIT_FAILED_LOGIN_ATTEMPTS=5`, `RATE_LIMIT_LOCKOUT_MINUTES=15` |
| `backend/pyproject.toml` | Add dependencies: `pydantic`, `python-jose[cryptography]` for JWT, `passlib[bcrypt]` for password hashing, `slowapi` for rate limiting (if not present) |
| `backend/tests/conftest.py` | Add pytest fixtures: `test_db`, `test_client`, `sample_user_payload` |
| `docs/architecture.md` | Document auth flow: register → JWT issuance → token refresh → logout |

## Files explicitly NOT touched

- `CLAUDE.md` — human-owned; AI forbidden to modify (Constitution P5).
- `specs/constitution.md`, `SPEC.md` — governing docs; not changed by execution.
- Any file owned by another feature (Constitution P6).

## Key execution decisions

1. **JWT vs session cookies:** Use JWT (stateless, works with frontend storing in memory per C-09). No session storage.
2. **Token storage in frontend:** Access token in memory only; refresh token also in memory (no localStorage/sessionStorage per C-09).
3. **Password hashing:** bcrypt with Passlib (industry standard, resistant to timing attacks).
4. **Rate limiting approach:** In-memory counter (SimpleLimiter or slowapi) for failed login attempts. For distributed deployments (future), switch to Redis.
5. **Location format:** Store as PostGIS POINT (lat, lon). Accept as JSON `{lat, lon}` or WKT in API. Validate bounds: ±90 lat, ±180 lon.
6. **Two signup endpoints:** POST `/auth/register` (customer only: email, password). POST `/auth/register-vendor` (vendor: email, password, shop_name, location, shop_description). Avoids role ambiguity in frontend form logic.
7. **Vendor shop details at signup:** Location required during registration, not post-onboarding. Simplifies vendor onboarding; they can update location later via PATCH.
8. **Email uniqueness:** UNIQUE constraint on `users.email` (case-insensitive via DB collation or app-level normalization).
9. **Refresh token rotation (mandatory):** On each `/auth/refresh` call, issue new refresh token + invalidate old one. Reduces security exposure if a token leaks.
10. **Rate limiting signup:** Max 10 registrations per IP per hour (env-configurable). Prevents spam/DDoS signup attempts.

## Architectural risks

- **R1 — In-memory rate limiting at scale:** Fails if multiple app instances run. Mitigation: add Redis backing for rate limit state (Phase 2, feature gate). Both login and signup rate limits affected.
- **R2 — JWT secret leakage:** If `JWT_SECRET` in env is compromised, all tokens are at risk. Mitigation: rotate secret regularly, use strong random generation, keep in HashiCorp Vault (future). Refresh token rotation (mandatory) limits exposure window.
- **R3 — Password reset missing:** Users cannot recover forgotten passwords. Mitigation: add password reset endpoint + email verification (feature flag, lower priority).
- **R4 — Refresh token storage race:** Client receives new refresh token from `/auth/refresh` in response; if connection drops, client may lose it or use old one. Mitigation: client retries refresh with old token if network error; server allows grace period (e.g., 60s) for old token reuse.
- **R5 — GET /me information leakage:** Returning vendor_id and shop details in /me response. Mitigation: only return if authenticated + user_type='vendor'; no exposure to customers.
- **R6 — Concurrent vendor registration:** Race condition if two requests for same email hit at same time. Mitigation: UNIQUE constraint catches this; app returns 409 or 400; client retries.

## Verification steps (post-implementation)

1. **Unit tests pass:** `make test` runs all `backend/tests/test_auth_*.py` with 100% pass rate.
2. **Manual: Register customer** — POST `/api/auth/register` with valid email/password → 201, get JWT with user_type='customer'.
3. **Manual: Register vendor** — POST `/api/auth/register-vendor` with shop details (name, lat/lon, description) → 201, vendor record created, JWT with user_type='vendor'.
4. **Manual: GET /me** — After login, call GET `/api/auth/me` with JWT → 200, return email, user_type, user_id. If vendor, also return vendor_id, shop_name, location. Without JWT → 401.
5. **Manual: Token refresh rotation** — Login, call `/api/auth/refresh` with refresh_token_1 → get new access token + refresh_token_2. Call `/api/auth/refresh` with refresh_token_1 again → 401 (old token revoked). Call with refresh_token_2 → 200 (new token works).
6. **Manual: Login & token expiry** — Login, wait until access token expires (or mock clock), call `/api/auth/refresh` → get new token. Old access token rejected.
7. **Manual: Logout revokes token** — Login, logout, try to refresh with revoked refresh token → 401. Attempt to use revoked token again → 401.
8. **Manual: Rate limiting login** — Intentionally fail login 5+ times in 15 min → requests blocked with 429. Wait 15 min (or mock), retry succeeds.
9. **Manual: Rate limiting signup** — Attempt 10+ registrations from same IP in 1 hour → requests blocked with 429. Different IP succeeds.
10. **Manual: Frontend integration** — Frontend on page load calls GET `/api/auth/me` to restore user context. Login calls `/api/auth/login`, stores access token in memory. Before expiry, calls `/api/auth/refresh` to get new token.
11. **Manual: Vendor location validation** — Register vendor with invalid lat/lon (>90, >180) → 400 with error message. Valid coordinates → 201.
12. **Lint & type check:** `make lint` and `ruff check .` pass (no errors, warnings acceptable).
13. **DB schema present:** Inspect PostgreSQL: `\dt` shows users, vendors, refresh_tokens tables with correct columns & indexes.

---
**STATUS: AWAITING APPROVAL.** No implementation file will be created or modified
until this plan is approved by the user.
