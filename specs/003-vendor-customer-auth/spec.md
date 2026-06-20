---
title: Feature 003: Vendor Customer Auth
feature: 003-vendor-customer-auth
status: draft
created: 2026-06-20
---

# Feature 003: Vendor Customer Auth — Specification

> Architectural contract for feature `003-vendor-customer-auth` (Constitution P3).
> Mark every unknown `[NEEDS CLARIFICATION: ...]` — never guess (Constitution P2).
> Outranked by `specs/constitution.md` and the master `SPEC.md`.

## 1. User Scenarios & Edge Cases

Primary scenarios (Given / When / Then), each with the edge cases it must handle.

1. **Scenario: Customer Registration & OTP Login**
   - *Given* a new customer with a phone number
   - *When* customer enters phone → system sends OTP via SMS → customer enters OTP code
   - *Then* customer is authenticated, receives access_token + refresh_token, can place orders
   - **Edge cases:** 
     - Empty/invalid phone number format
     - OTP expired (>10 minutes) before verification
     - Wrong OTP code entered 3 times → block for 5 minutes
     - Duplicate phone already registered
     - Concurrent OTP requests for same phone

2. **Scenario: Vendor Registration & Onboarding**
   - *Given* a new vendor with phone and shop details
   - *When* vendor enters phone → receives OTP → verifies OTP → enters shop name, location (lat/lng), category
   - *Then* vendor account created with role=`vendor`, shop location stored as PostGIS Point, receives auth tokens
   - **Edge cases:**
     - Missing shop location coordinates
     - Invalid lat/lng (outside [-90,90] / [-180,180])
     - Duplicate shop name or location
     - Shop name with SQL injection / XSS attempts → sanitize
     - Multiple vendors requesting same location simultaneously

3. **Scenario: Token Refresh & Session Extension**
   - *Given* customer/vendor with valid refresh_token but expired access_token
   - *When* client calls `/auth/refresh` with refresh_token
   - *Then* new access_token issued, refresh_token rotated (old one revoked)
   - **Edge cases:**
     - Refresh token expired or revoked
     - Refresh token reuse attack (token already used)
     - User logged out on another device → refresh should fail

4. **Scenario: Logout & Token Revocation**
   - *Given* authenticated user with active session
   - *When* user calls `/auth/logout`
   - *Then* refresh_token marked revoked in DB, user must re-authenticate
   - **Edge cases:**
     - Logout called multiple times
     - Token already expired

## 2. Functional Requirements & Decisions

Each requirement is testable; each records the decision taken (and why) so the
"how" is auditable. Open points stay `[NEEDS CLARIFICATION]`.

| ID | Requirement (MUST/SHOULD) | Decision taken & rationale |
| :-- | :-- | :-- |
| FR-1 | MUST: OTP-based authentication for both customer & vendor | OTP eliminates password management burden; aligns with phone-first UX in developing markets |
| FR-2 | MUST: OTP validity = 10 minutes | Balance: 10 min is long enough for user to receive SMS + enter, short enough for security (limits brute force window) |
| FR-3 | MUST: OTP max failed attempts = 3; then 5-min lockout | Prevents OTP brute force; 5-min lockout is strict but recoverable |
| FR-4 | MUST: JWT access token expiry = 1 hour | Short-lived reduces breach window; refresh token handles longer sessions |
| FR-5 | MUST: JWT refresh token expiry = 30 days | Standard web app convention; enables 30-day "remember me" sessions |
| FR-6 | MUST: Refresh token stored as bcrypt hash in DB | Prevents DB breach from leaking active tokens; aligns with OWASP |
| FR-7 | MUST: Refresh token rotation on use | Invalidates old token after refresh, mitigates token-reuse attacks |
| FR-8 | MUST: Users table has `role` enum (customer \| vendor) | Single table, simpler auth logic; roles determine API access |
| FR-9 | MUST: Vendor location stored as PostGIS Point | Enables distance-based queries for proximity search (Akash's feature); required for §6 non-functional "proximity ≤5km" |
| FR-10 | MUST: All text inputs (phone, shop_name, etc.) sanitized | Prevents SQL injection & XSS; Constitution P2 (security surface) |
| FR-11 | SHOULD: OTP sent via SMS (integration stub for now) | Real SMS integration deferred; test uses mock SMS provider |
| FR-12 | MUST: Phone number stored in normalized format (E.164) | e.g. "+91-9876543210"; enables deduplication and international portability |
| FR-13 | MUST: API rate-limiting on `/auth/send-otp` | Max 5 OTP requests per phone per hour, prevent SMS spam/abuse |
| FR-14 | MUST: Vendor onboarding requires shop_location (lat, lng) | Non-negotiable for proximity queries; register/verify flow must not skip it |

## 3. Success Criteria / Acceptance Criteria

Objective, verifiable criteria that mark this feature "done & correct".

- [ ] Customer can register via OTP: `POST /auth/register-customer` accepts phone → `POST /auth/send-otp` sends OTP → `POST /auth/verify-otp` verifies → returns `{access_token, refresh_token}`
- [ ] Vendor can register & onboard: `POST /auth/register-vendor` accepts phone, shop_name, shop_location (lat, lng) → sends OTP → verify → returns tokens + vendor_id
- [ ] User can refresh expired access_token: `POST /auth/refresh` with valid refresh_token → returns new access_token + rotated refresh_token
- [ ] User can logout: `POST /auth/logout` revokes refresh_token; subsequent refresh attempts fail with 401 Unauthorized
- [ ] All endpoints return proper error codes: 400 (bad input), 401 (unauthorized), 409 (conflict: duplicate phone/shop), 429 (rate limit exceeded), 500 (internal error)
- [ ] All text inputs (phone, shop_name, etc.) are sanitized (no SQL injection, no XSS); passed to DB safely
- [ ] OTP code is 6 digits, expires in 10 minutes, can be verified once
- [ ] Access token (JWT): includes user_id, role, issued_at; expires in 1 hour; verified by signature on each protected endpoint
- [ ] Refresh token (JWT): includes user_id, jti (unique ID); expires in 30 days; stored as bcrypt hash in `refresh_tokens` table
- [ ] Vendor location (lat, lng) is validated (lat ∈ [-90,90], lng ∈ [-180,180]); stored as PostGIS Point; indexed for proximity queries
- [ ] Database schema: `users`, `vendors`, `otps`, `refresh_tokens` tables created with correct columns, types, PKs, FKs, indexes
- [ ] Rate limiting: max 5 OTP requests per phone per hour (returns 429 if exceeded)
- [ ] Concurrency safe: simultaneous register requests for same phone → only one succeeds (unique constraint on phone)
- [ ] All changes committed: spec.md, plan.md, prompts.md, conversation-history.md in `specs/003-vendor-customer-auth/`
- [ ] Tests pass: `pytest backend/tests/test_auth.py` (register, OTP flow, refresh, logout, error cases all covered)
- [ ] Linting clean: `ruff check .` passes

## 4. DB Schema Entities

Entities introduced/changed by this feature (tables, key columns, types,
relationships, indexes/extensions). Migrations live in `backend/migrations/`.

| Entity | Key fields (type) | Relationships | Notes (indexes / constraints) |
| :-- | :-- | :-- | :-- |
| `users` | `id` (UUID, PK), `phone` (VARCHAR(15), unique, not null), `role` (ENUM: customer\|vendor, not null), `created_at` (TIMESTAMP), `updated_at` (TIMESTAMP) | 1→many `vendors`, 1→many `otps`, 1→many `refresh_tokens` | INDEX on `phone` for OTP lookup; UNIQUE constraint on `phone` (no duplicate registrations) |
| `vendors` | `id` (UUID, PK), `user_id` (UUID, FK→users.id, not null), `shop_name` (VARCHAR(255), not null), `shop_location` (Point, PostGIS, not null), `created_at` (TIMESTAMP), `updated_at` (TIMESTAMP) | many→1 `users` | UNIQUE constraint on `shop_name` (or allow duplicates? [NEEDS CLARIFICATION]); SPATIAL INDEX on `shop_location` for proximity queries; FOREIGN KEY on `user_id` (ON DELETE CASCADE) |
| `otps` | `id` (UUID, PK), `user_id` (UUID, FK→users.id, not null), `code` (VARCHAR(6), not null), `expires_at` (TIMESTAMP, not null), `used` (BOOLEAN, default false), `created_at` (TIMESTAMP) | many→1 `users` | INDEX on `user_id` for OTP lookup; INDEX on `expires_at` for cleanup queries; OTP considered expired if current_time > expires_at |
| `refresh_tokens` | `id` (UUID, PK), `user_id` (UUID, FK→users.id, not null), `token_hash` (VARCHAR(255), unique, not null), `expires_at` (TIMESTAMP, not null), `revoked` (BOOLEAN, default false), `created_at` (TIMESTAMP) | many→1 `users` | INDEX on `user_id` for per-user token lookup; UNIQUE constraint on `token_hash` (prevent accidental reuse); INDEX on `expires_at` for cleanup; revoked flag allows explicit logout before expiry |

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
