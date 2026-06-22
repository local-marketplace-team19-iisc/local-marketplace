---
title: Feature 003: Vendor Customer Auth
feature: 003-vendor-customer-auth
status: draft
created: 2026-06-21
---

# Feature 003: Vendor Customer Auth — Specification

> Architectural contract for feature `003-vendor-customer-auth` (Constitution P3).
> Mark every unknown `[NEEDS CLARIFICATION: ...]` — never guess (Constitution P2).
> Outranked by `specs/constitution.md` and the master `SPEC.md`.

## 1. User Scenarios & Edge Cases

Primary scenarios (Given / When / Then), each with the edge cases it must handle.

1. **Scenario: Customer Registration & Login**
   - *Given* a new user on the marketplace homepage
   - *When* they click "Register" and enter email, password (confirmation), and agree to ToS
   - *Then* account is created, JWT token issued, user redirected to marketplace
   - **Edge cases:**
     - Email already registered → validation error
     - Weak password → validation error (min 8 chars, complexity rules)
     - Password mismatch → validation error
     - Duplicate signup request (race condition) → idempotent, return existing user's token

2. **Scenario: Customer Login**
   - *Given* a registered customer with valid credentials
   - *When* they enter email and password
   - *Then* JWT access token issued, stored in memory (never localStorage per C-09)
   - **Edge cases:**
     - Wrong email or password → "Invalid credentials" (generic, no user enumeration)
     - Account locked after N failed attempts → reject with "Account temporarily locked"
     - Email not verified (future: if verification added) → reject with clear message

3. **Scenario: Vendor Registration & Onboarding**
   - *Given* a new vendor (shop owner) on signup page
   - *When* they register (email, password) + enter shop details (name, location/coordinates, description)
   - *Then* vendor account created, shop record linked, JWT issued, redirected to vendor dashboard
   - **Edge cases:**
     - Missing shop location → validation error
     - Duplicate shop name in same area → warning (allow, but should be unique per business logic—TBD)
     - Invalid coordinates → validation error

4. **Scenario: Token Refresh**
   - *Given* a client with an expired access token but valid refresh token
   - *When* they call POST `/auth/refresh` with the refresh token
   - *Then* new access token issued, refresh token may be rotated
   - **Edge cases:**
     - Refresh token expired → reject, user must login again
     - Refresh token revoked (logout call) → reject
     - No refresh token provided → reject

5. **Scenario: Get Current User Info**
   - *Given* an authenticated user with valid JWT
   - *When* frontend calls GET `/api/auth/me`
   - *Then* return user details (id, email, user_type, vendor_id if vendor, shop_name if vendor)
   - **Edge cases:**
     - No/invalid JWT → 401 Unauthorized
     - User deleted after token issued → 404 or return minimal info

6. **Scenario: Logout**
   - *Given* an authenticated user with active tokens
   - *When* they click "Logout"
   - *Then* refresh token revoked server-side, frontend clears in-memory JWT
   - **Edge cases:**
     - Already logged out → idempotent, return success
     - Stale token → accept logout (best effort)

## 2. Functional Requirements & Decisions

Each requirement is testable; each records the decision taken (and why) so the
"how" is auditable. Open points stay `[NEEDS CLARIFICATION]`.

| ID | Requirement (MUST/SHOULD) | Decision taken & rationale |
| :-- | :-- | :-- |
| FR-1 | MUST: Email/password registration (customer & vendor) | No OTP/SMS. Email validation via regex; password validation (min 8 chars, regex for complexity). Aligns with frontend already built. |
| FR-2 | MUST: Email/password login | Return JWT access + refresh tokens on success. Access token in memory only (C-09). |
| FR-3 | MUST: JWT token generation & validation | Use HS256 (symmetric key in env). Access token TTL: 1h (configurable). Refresh token TTL: 7d (configurable). Payload: user_id, user_type (customer\|vendor), email. |
| FR-4 | MUST: Token refresh endpoint | POST `/auth/refresh` accepts refresh token, returns new access token + optionally rotated refresh token. |
| FR-5 | MUST: Logout endpoint | POST `/auth/logout` revokes refresh token (marks as used/deleted). Idempotent. |
| FR-6 | MUST: Vendor registration includes shop location | Register endpoint accepts shop_name, location (lat/lon or PostGIS geometry), shop_description. Creates both user & vendor record. |
| FR-7 | SHOULD: Password strength validation | Min 8 chars, at least 1 uppercase, 1 digit, 1 special char. Clear error messages. |
| FR-8 | MUST: Account enumeration prevention | Login/register endpoints return generic "Invalid credentials" or "Email already registered" (no leak of which emails exist). |
| FR-9 | SHOULD: Rate limiting on login attempts | Max 5 failed attempts in 15 min → lock for 15 min. Configurable per env. |
| FR-9b | SHOULD: Rate limiting on register attempts | Max 10 new registrations per IP per hour. Prevents spam signups. |
| FR-10 | MUST: Distinguish customer vs vendor in JWT | user_type field in token payload. Backend uses this to enforce authorization (vendor-only endpoints). |
| FR-11 | MUST: GET /api/auth/me endpoint | Return current user's email, user_type, user_id, vendor_id (if vendor), shop_name/location (if vendor). Requires valid JWT. |
| FR-12 | MUST: Two separate signup endpoints | POST `/auth/register` for customers (email, password only). POST `/auth/register-vendor` for vendors (email, password, shop_name, location, shop_description). Avoids role confusion in frontend form. |
| FR-13 | MUST: Vendor shop details at signup | Shop location (lat/lon) required during vendor registration (not post-onboarding). Simplifies flow; vendor can edit later. |
| FR-14 | MUST: Refresh token rotation | Issue new refresh token on each `/auth/refresh` call; old token revoked. Reduces exposure window if token compromised. |

## 3. Success Criteria / Acceptance Criteria

Objective, verifiable criteria that mark this feature "done & correct".

- [ ] POST `/auth/register` creates a customer with email, password (hashed), returns JWT (access + refresh) + user_id + user_type='customer'
- [ ] POST `/auth/register-vendor` creates vendor + user, requires shop_name, shop_location (lat/lon), returns JWT + vendor_id + user_type='vendor'
- [ ] POST `/auth/login` accepts email + password, validates, returns JWT (access + refresh) + user_type or generic error
- [ ] GET `/api/auth/me` returns user email, user_type, user_id, vendor_id/shop_name/location if vendor; requires valid JWT; 401 if missing/invalid
- [ ] POST `/auth/refresh` accepts valid refresh token, issues new access token + NEW refresh token (rotated), invalidates old refresh token
- [ ] POST `/auth/logout` revokes refresh token; subsequent refresh calls with that token reject (401)
- [ ] JWT access token expires after 1h (configurable); refresh token after 7d
- [ ] Password hashing uses bcrypt (not plaintext or weak hash)
- [ ] All endpoints return appropriate HTTP status (201 created, 200 ok, 400 bad request, 401 unauthorized, 429 rate limit)
- [ ] Rate limiting: max 5 failed logins in 15 min; max 10 registrations per IP per hour
- [ ] Frontend stores access token in memory, calls `/auth/me` on page load to restore user context, calls `/auth/refresh` before expiry
- [ ] Register endpoint validates shop location (±90 lat, ±180 lon) for vendor signups
- [ ] Vendor & customer token payloads differ in user_type; vendor endpoints enforce authorization
- [ ] All tests pass; no unresolved `[NEEDS CLARIFICATION]` in spec.md

## 4. DB Schema Entities

Entities introduced/changed by this feature (tables, key columns, types,
relationships, indexes/extensions). Migrations live in `backend/migrations/`.

| Entity | Key fields (type) | Relationships | Notes (indexes / constraints) |
| :-- | :-- | :-- | :-- |
| users | id (UUID, PK), email (VARCHAR 255), password_hash (VARCHAR 255), user_type (ENUM: 'customer' \| 'vendor'), created_at (TIMESTAMP), updated_at (TIMESTAMP) | 1→1 vendors (if user_type='vendor') | UNIQUE(email); idx on user_type; idx on created_at for audit |
| vendors | id (UUID, PK), user_id (UUID, FK→users), shop_name (VARCHAR 255), location (PostGIS POINT), shop_description (TEXT), is_active (BOOL, default true), created_at (TIMESTAMP), updated_at (TIMESTAMP) | 1→1 users; 1→N vendors_catalog (future) | UNIQUE(user_id); idx on location for geo queries; idx on is_active |
| refresh_tokens | id (UUID, PK), user_id (UUID, FK→users), token_hash (VARCHAR 255), expires_at (TIMESTAMP), revoked_at (TIMESTAMP, nullable), created_at (TIMESTAMP) | N→1 users | UNIQUE(token_hash); idx on user_id, expires_at for cleanup; idx on revoked_at for audit |

## 5. Requirement Completeness / Definition of Done

This feature is DONE only when **all** hold:

- [ ] No unresolved `[NEEDS CLARIFICATION]` markers remain (Constitution P2).
- [ ] `plan.md` was written and **user-approved** before any implementation (P1).
- [ ] All Functional Requirements (§2) have passing tests.
- [ ] All Success/Acceptance Criteria (§3) are met and verified.
- [ ] DB entities (§4) are migrated; schema matches the spec.
- [ ] `make test` green and `make lint` clean.
- [ ] Audit trail current: `spec.md`, `plan.md`, `prompts.md`,
      `conversation-history.md` all committed (P3).
- [ ] `docs/architecture.md` updated with any decision this feature introduced.
