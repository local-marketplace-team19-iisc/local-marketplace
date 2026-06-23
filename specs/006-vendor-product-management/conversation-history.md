# Feature 006 — Conversation History

Append-only session log (Constitution P3 / P7). Earlier entries are never edited.

---

## Session 1 — 2026-06-23 — Spec & plan authoring (pre-implementation)

**Context / goal.** Implement the vendor product workflow end-to-end (create a
product from a typed/spoken description; delete a vendor's own product by
description), persisting the Feature 005 catalog schema. Frontend design from
Feature 004 is the reference; 005 spec is the schema authority and must not be
rewritten.

**Files read first (per request):** `specs/005-catalog/spec.md`,
`frontend/src/pages/VendorPage.jsx`, `.../ProductExtractPanel.jsx`,
`.../services/productService.js`, `backend/app/catalog/models.py` (+`enums.py`),
`backend/app/main.py`, `backend/app/db/session.py`, `backend/app/models/vendor.py`
(+`user.py`), all `backend/migrations/versions/*`. Also read for context: auth
route/service/schemas, frontend `apiClient.js`, `constants.js`, `_mocks/index.js`,
`extractService.js`, helpers/validators, `docker-compose.yml`, `.env.example`,
`backend/db/init/01-extensions.sql`, the constitution.

**Key findings.**
- App ships with two configs: SQLite default in `core/config.py`, but
  docker-compose + `.env.example` point at PostgreSQL (`postgresql+psycopg`).
  Existing Alembic migrations (`0001`–`0003`) are Postgres-only
  (postgis/geoalchemy2/`postgresql.UUID`) and cannot apply to SQLite; nothing
  calls `create_all` at startup.
- Codebase quirk: ORM ids are `String(36)` while migrations emit `UUID`. 006
  follows this convention rather than changing it (003-owned files).
- 005 makes `subcategory_id` NOT NULL; product also requires brand/unit/price.
  Free-text descriptions won't always carry these → needs fallbacks.
- Frontend defaults to `VITE_USE_MOCKS=true`; product shape is
  `{id,name,price,stock,category,description,vendorId,...}`.

**Decisions (4 forks resolved with user via AskUserQuestion).**
1. Runtime = **PostgreSQL**; new tables via Alembic `0004` (down_revision `0003`).
2. Unrecognized category → seeded **General → General** subcategory (keep NOT NULL).
3. Parser defaults: brand `"Generic"`, `PIECE`/`1`, stock `0`; **missing price → reject** (005 FR-16).
4. Seed taxonomy derived from 005 examples + frontend `PRODUCT_CATEGORIES`.

**Additional design decisions (mine, recorded for audit).**
- `products` adds the four 005-deferred operational fields: `vendor_id`,
  `stock_quantity`, `created_at`, `updated_at`.
- Writes are vendor-scoped via the 003 JWT; reads are open.
- `delete-by-description` scores the vendor's own rows (keyword overlap), deletes
  the single best match, `404` if none.
- `GET /api/products` returns display aliases + raw catalog fields so VendorPage
  renders unchanged.
- Tests run on in-memory SQLite (portable ORM types) for speed; runtime is Postgres.

**Edge cases / unknowns surfaced.** Missing price (reject), unknown category
(General), ambiguous delete match (best score, deterministic tiebreak by
`created_at`), cross-vendor delete attempt (filtered out), mock-mode parity for the
two new endpoints.

**Artifacts written this session:** `spec.md`, `plan.md`, `prompts.md`,
`conversation-history.md`; `.active_feature` → `006-vendor-product-management`.

**Status.** Awaiting user approval of `plan.md` before writing implementation
files (Constitution P1). No implementation files created yet.

---

## Session 2 — 2026-06-23 — Implementation (plan approved)

**Context / goal.** User approved `plan.md`. Implemented M1–M10.

**Files created.**
- Models: `backend/app/models/category.py`, `subcategory.py`, `product.py`
  (registered in `models/__init__.py`).
- Migration: `backend/migrations/versions/0004_create_catalog_products.py`
  (unit_type enum + 3 tables + seeded taxonomy via `op.bulk_insert`).
- `backend/app/catalog/seed_data.py` (single taxonomy source; uuid5-stable ids).
- `backend/app/catalog/parser.py` (deterministic description parser).
- `backend/app/schemas/product.py` (registered in `schemas/__init__.py`).
- `backend/app/services/product_service.py` (registered in `services/__init__.py`).
- Routes `backend/app/api/routes/products.py`, `catalog.py` (registered in
  `routes/__init__.py`; wired into `main.py`).
- Tests `backend/tests/test_product_parser.py`,
  `test_products_from_description.py`, `test_products_delete_by_description.py`;
  `catalog_db` fixture appended to `backend/tests/conftest.py`.

**Files modified (additive).** `backend/app/main.py` (Swagger on + routers),
the three `__init__.py` registries, `frontend/src/utils/constants.js`,
`frontend/src/services/productService.js`,
`frontend/src/components/products/ProductExtractPanel.jsx`,
`frontend/src/pages/VendorPage.jsx`, `frontend/src/services/_mocks/index.js`,
`docs/architecture.md`.

**Decisions/refinements during build.**
- Moved the shared test fixture into `conftest.py` (idiomatic; resolved ruff
  F811 from importing a fixture) instead of a helper module — deviates from the
  plan's "conftest untouched" note but is additive and cleaner.
- Test fixture seeds `vend-1`/`vend-2` to cover the ownership path.

**Verification.**
- Backend imports clean; FastAPI exposes `/api/products*`, `/api/catalog/*`,
  `/docs`, `/openapi.json`. End-to-end create/delete confirmed on in-memory SQLite.
- 006 tests: **13 passed**. Ruff: clean on all 006 files.
- Frontend: `npm run lint` clean, `npm run build` succeeds.

**Edge cases / conflicts surfaced.**
- ⚠️ `test_health.py::test_no_route_other_than_health` (000-owned) now fails
  because Swagger was enabled per the explicit feature request (SPEC §7 says
  auto-docs off). Left untouched pending a human decision (Constitution P5).
- ⚠️ Pre-existing env failure: `bcrypt 5.0.0` vs pinned `passlib 1.7.4` breaks the
  003 auth/password tests (`password cannot be longer than 72 bytes`). Not a 006
  defect; pinning `bcrypt<4.1` would fix but touches 003/governance config.

**Open items before "done".** Live PostgreSQL verification
(`docker compose up db` → `alembic upgrade head` → real create/delete via
`/docs`) not yet run in this environment; the two conflicts above need a human
call.

---

## Session 3 — 2026-06-23 — Live PostgreSQL verification

**Context / goal.** User brought Docker up and asked to run the live Postgres
verification.

**What happened.** `docker compose up -d db` built/started the PostGIS+pgvector
image (healthy; `marketplace/marketplace@localhost:5432/marketplace`). Running
`alembic upgrade head` surfaced a cascade of **pre-existing, Postgres-only bugs in
the 003 migration/auth code** (all latent because 003 was only ever run on SQLite):
1. `0001` created the `user_role` enum twice (explicit `.create()` **and** the
   `users.role` column). **Fixed with user approval** — dropped the redundant
   explicit `.create()` so `create_table` creates it once.
2. `0002` adds `attempts`/`locked_until` to `otps`, but `0001` already defines
   them → `DuplicateColumn`. (Not fixed — 003-owned, out of 006 scope.)
3. ORM divergence: `otps`/`refresh_tokens` models use `UUID` ids while `users`
   uses `String(36)` → FK type mismatch under `create_all` on PG.
4. Auth layer: `jwt_service.verify_token` returns `user_id` as `uuid.UUID`, but
   `users.id` is `VARCHAR(36)` → `operator does not exist: character varying = uuid`
   on the vendor-authenticated routes.

**Conclusion.** The 003 migration chain + auth code are stale/divergent from the
ORM and broken on Postgres in several independent ways — a 003 rework, outside
006. 006 itself was verified on **real Postgres** two ways:
- **Schema/DDL:** built the 006 tables from the ORM (`create_all` of
  users/vendors/categories/subcategories/products — all `String(36)`, consistent)
  and via a direct `psql` INSERT into `products` (enum `LITER`, `numeric` price,
  seeded `Milk` subcategory, vendor FK) — succeeded.
- **Service path:** `create_from_description` / `list_products` /
  `delete_by_description` exercised against the live PG session — create persists,
  missing-price rejected, delete removes, cross-vendor delete blocked. Final row
  confirmed via `psql`.
- **Live routes on PG:** `GET /api/catalog/categories` → 200 (12 cats / 16 subs);
  unauthenticated write → 401. The vendor-authenticated HTTP routes could not be
  exercised on PG **only** because of 003 auth bug #4 above (works on SQLite — see
  the 13 green unit tests).

**Files altered this session.** `backend/migrations/versions/0001_create_auth_tables.py`
(approved 1-line-class fix to the enum creation). No 006 files changed.

**Status.** 006 verified on Postgres (schema + service) and on SQLite (routes +
13 tests). Remaining: `alembic upgrade head` and PG vendor-route auth are blocked
by pre-existing 003 defects that need a separate, human-owned 003 fix.

---

## Session 4 — 2026-06-23 — Real-backend frontend enablement (user-approved)

**Context / goal.** User asked to test the 006 vendor flow through the real
frontend against the real backend (SQLite), and approved the enabling fixes.

**Enabling fixes (outside 006, approved).**
- `backend/app/services/jwt_service.py` — `verify_token`/`verify_refresh_token`
  now return `user_id` as **str** (was `uuid.UUID`). User ids are `String(36)`, so
  the UUID form never matched on SQLite ("User not found") and errored on Postgres.
  This unblocks `/api/auth/me` and all vendor-scoped routes.
- `backend/tests/test_jwt_service.py` — updated 4 assertions to the corrected str
  contract (`== str(user_id)`).
- `frontend/src/services/authService.js` — adapter mapping the real backend's
  `{access_token, user_type, …}` + `GET /api/auth/me` into the `{token, user}`
  shape `authContext` expects (vendorId/role/email). Mock responses pass through
  unchanged, so mock mode still works.
- Pinned `bcrypt==4.0.1` in the env (passlib 1.7.4 incompatible with bcrypt 5.0)
  so registration/login hashing works. Seeded a demo vendor in the SQLite DB:
  `vendor@demo.com` / `Demo1234!`. Created the 006 tables + taxonomy in
  `./local_marketplace.db` (create_all subset; the 003 Alembic chain can't run on
  SQLite). `frontend/.env` → `VITE_USE_MOCKS=false`.

**Verification (real backend over HTTP).** login → token; `/api/auth/me` → vendor
profile; `POST /api/products/from-description` ("Amul Butter 100g, Rs 58, 30 in
stock, Dairy") → persisted (`Amul | 58.0 | GRAM | 30 | Dairy`); list → 1;
`delete-by-description` "remove the butter" → removed; UTF-8 `₹110` create →
`Tropicana Orange Juice | MILLILITER 1000 | Beverages`. jwt + 006 tests: 25 passed,
ruff clean, eslint clean. Stack live: backend `:8000`, Swagger `/docs`, frontend
`:5173`.

**Response-envelope fix (006).** Browser testing surfaced that the frontend
expects `{ products: [...] }` / `{ product: {...} }` envelopes (the mock-layer
contract), but the routes returned bare `list[ProductRead]` / `ProductRead` →
`Cannot read properties of undefined (reading 'filter')` in `VendorPage.load`.
Wrapped the product routes with `ProductListResponse`/`ProductResponse` to match
the frontend contract (006 files only; service-level unit tests unaffected).

**Not fixed (pre-existing 003, out of scope).** `auth_register` tests
(`422` vs `400` for short password) and the broader Alembic chain on Postgres.
Vendor self-registration via the UI still hits the customer-only
`/api/auth/register` (the frontend doesn't call `register-vendor`); use the seeded
demo vendor for the vendor flow.
