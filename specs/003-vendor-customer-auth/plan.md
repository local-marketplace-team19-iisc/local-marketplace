# Plan — Feature 003: Vendor Customer Auth (Dry-Run)

> **Iron-Clad Rule (Constitution P1 / SPEC §8):** this dry-run MUST be reviewed and
> **approved by the user** before any implementation file is created or modified.

## Scope

**Delivers:** OTP-based registration/login for customer and vendor roles, JWT
access + refresh token issuance, refresh-token rotation, logout/revocation,
vendor onboarding with PostGIS shop location, and the supporting `users`,
`vendors`, `otps`, `refresh_tokens` tables (per spec.md §4).

**Out of scope:** real SMS provider integration (FR-11 stubs/mocks it),
password-based login, social/OAuth login, proximity search itself (consumer of
`shop_location`, owned by another feature), admin/back-office auth.

## Files to CREATE

| Path | Purpose |
| :-- | :-- |
| `backend/app/models/user.py` | SQLAlchemy model for `users` table (id, phone, role, timestamps) |
| `backend/app/models/vendor.py` | SQLAlchemy model for `vendors` table incl. PostGIS `shop_location` |
| `backend/app/models/otp.py` | SQLAlchemy model for `otps` table |
| `backend/app/models/refresh_token.py` | SQLAlchemy model for `refresh_tokens` table |
| `backend/app/schemas/auth.py` | Pydantic request/response schemas (register, send-otp, verify-otp, refresh, logout) |
| `backend/app/api/auth.py` | FastAPI router: `/auth/register-customer`, `/auth/register-vendor`, `/auth/send-otp`, `/auth/verify-otp`, `/auth/refresh`, `/auth/logout` |
| `backend/app/services/otp_service.py` | OTP generation, expiry, attempt-counting, lockout logic (FR-2, FR-3) |
| `backend/app/services/token_service.py` | JWT issuance/verification, refresh-token rotation & bcrypt hashing (FR-4–FR-7) |
| `backend/app/services/sms_provider.py` | SMS-send interface + mock implementation (FR-11) |
| `backend/app/core/rate_limit.py` | Rate-limiting helper for `/auth/send-otp` (FR-13) |
| `backend/migrations/<timestamp>_create_auth_tables.py` | Migration creating `users`, `vendors`, `otps`, `refresh_tokens` + PostGIS extension/spatial index |
| `backend/tests/test_auth.py` | Tests covering register, OTP flow, refresh, logout, error/edge cases |

## Files to MODIFY (append/merge only — Constitution P6)

| Path | Change |
| :-- | :-- |
| `backend/app/main.py` | Register the new `auth` router |
| `backend/app/core/config.py` | Append JWT secret/expiry settings, OTP settings, rate-limit settings (env-driven) |
| `.env.example` | Append placeholder vars for JWT secret, OTP/SMS config |
| `docs/architecture.md` | Append decision log entries for OTP-only auth, token rotation, PostGIS location storage |

## Files explicitly NOT touched

- `CLAUDE.md` — human-owned; AI forbidden to modify (Constitution P5).
- `specs/constitution.md`, `SPEC.md` — governing docs; not changed by execution.
- Any file owned by another feature (Constitution P6).

## Key execution decisions

1. **Directory layout:** Use `backend/app/models/` (simpler, matches 000 scaffold pattern)
2. **ORM/migration:** SQLAlchemy + Alembic (standard choice; coordinated with Shubham's DB feature)
3. **Shop name uniqueness:** Allow duplicates (multiple vendors can have same name in different locations; only location + shop_name together must be unique)
4. **PostGIS availability:** Use Docker Postgres for dev/test (safer than assuming local PostGIS; `docker-compose.yml` extended with DB service)
5. **SMS provider:** Mock SMS implementation (FR-11 "stub"; real SMS deferred to later feature)
6. **Rate-limiting:** In-memory counter per phone number (simplest for MVP; Redis if needed later for multi-instance)

## Architectural risks

- **R1** — **PostGIS in Docker:** Migration script must enable `CREATE EXTENSION postgis` in test DB. Mitigated by docker-compose.yml DB service config.
- **R2** — **Mock SMS in prod:** Mock provider logs OTPs to stdout/log (unsafe for production). Mitigation: real SMS provider integration (feature 004+) required before production release.
- **R3** — **In-memory rate-limit:** Rate limits reset if app restarts; does not persist across instances. Acceptable for MVP; Redis backing deferred.
- **R4** — **Token rotation complexity:** Refresh token rotation requires invalidating old token immediately. Risk: race condition if client requests refresh twice concurrently. Mitigation: DB transaction ensures only one refresh succeeds (FK constraint + unique jti).
- **R5** — **Dependency on shop_location for vendor onboarding:** PostGIS Point type requires migration + spatial index. Coordinates Shubham's DB schema feature; if DB schema feature delayed, this blocks. Mitigation: coordinate early with Shubham.

## Verification steps (post-implementation)

1. **pytest cases mapped to spec.md §3 acceptance criteria:**
   - test_customer_register_and_login (phone → OTP → verify → tokens)
   - test_vendor_register_and_onboarding (phone → OTP → verify + shop details → tokens)
   - test_otp_expiry (OTP invalid after 10 min)
   - test_otp_lockout (3 failed attempts → 5-min lockout)
   - test_refresh_token_rotation (refresh endpoint issues new token, old revoked)
   - test_logout_revokes_token (logout → refresh fails)
   - test_rate_limit_send_otp (5 requests/hour/phone → 429 on 6th)
   - test_input_sanitization (SQL injection/XSS attempts safely rejected)
   - test_vendor_location_validation (invalid lat/lng rejected)
   - test_duplicate_phone_prevented (concurrent register same phone → only one succeeds)
2. `make test` green, `make lint` clean (per spec.md §5 Definition of Done).
3. Manual smoke test: run `docker-compose up` → POST /auth/register-customer with phone → receive OTP → POST /auth/verify-otp → get tokens → POST /auth/refresh → get new access_token → POST /auth/logout → refresh fails with 401.

---
**STATUS: AWAITING APPROVAL.** No implementation file will be created or modified
until this plan is approved by the user.
