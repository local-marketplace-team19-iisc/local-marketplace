# Feature 006: Vendor Product Management — Implementation Plan (Dry-Run)

> Constitution P1: this plan must be **user-approved** before any implementation
> file is created or modified. It is a dry-run: each milestone names the exact
> files, the order, and the verification.

## 0. Resolved decisions (from 2026-06-23 Q&A)

| Fork | Decision |
| :-- | :-- |
| Runtime DB / table creation | **PostgreSQL** (docker-compose / `postgresql+psycopg`). Tables created by **Alembic `0004`** (down_revision `0003`). No `create_all` in app startup. |
| Unknown category | Assign seeded **General → General** subcategory (keeps 005 `subcategory_id` NOT NULL). |
| Parser defaults | `brand="Generic"`, `unit_type=PIECE`, `unit_value=1`, `stock_quantity=0`. Missing **price → reject** (005 FR-16). |
| Seed taxonomy | Derived from 005 examples + frontend `PRODUCT_CATEGORIES`, each with a `General` subcategory + a global `General → General` fallback. |

## 1. Conventions reused (no new abstractions)

- **ID columns:** Alembic `postgresql.UUID`; ORM `String(36)` — exactly as `users`/`vendors`.
- **Enum type:** create a Postgres `unit_type` enum in the migration (mirrors `user_role`); ORM uses `sa.Enum(UnitType)` (portable to SQLite for tests).
- **Auth:** reuse `auth_service.get_current_user(db, token)` + a `get_current_vendor` dependency in the new router (same `Bearer` extraction as `auth.py::get_current_user`).
- **Service layer:** new `backend/app/services/product_service.py` mirrors `auth_service.py` (plain functions, raises typed errors mapped to HTTP in the route).
- **Validation:** reuse the 005 Pydantic rules (price 2-dp, unit>0, brand sentinel) inside the request schemas.

## 2. Milestones (build order)

### M1 — Models (`backend/app/models/`)
- `category.py` → `Category` (String(36) PK, name unique, parent_category_id null).
- `subcategory.py` → `SubCategory` (FK→categories).
- `product.py` → `Product` (005 fields + FR-2 fields; `Enum(UnitType)`, `Numeric`).
- Register all three in `backend/app/models/__init__.py` (append to `__all__` — P6 merge, no overwrite) so Alembic autogen/metadata sees them.
- **Verify:** `python -c "import backend.app.models"` imports clean; `Base.metadata` lists the 3 tables.

### M2 — Migration (`backend/migrations/versions/0004_create_catalog_products.py`)
- `revision="0004_create_catalog_products"`, `down_revision="0003_add_email_password_auth"`.
- Create `unit_type` enum; create `categories`, `subcategories`, `products` (UUID, Numeric, FKs, indexes on `vendor_id`/`subcategory_id`).
- `op.bulk_insert` the seeded taxonomy (fixed UUIDs from `catalog/seed_data.py`).
- `downgrade()` drops products → subcategories → categories → enum.
- **Verify:** `alembic upgrade head` then `alembic downgrade -1` round-trips (against Postgres).

### M3 — Seed source (`backend/app/catalog/seed_data.py`)
- One module: `CATEGORIES`, `SUBCATEGORIES` lists with stable UUIDs + the `General` fallback ids exported as constants. Imported by the migration **and** the tests (single source — not an abstraction layer, just data).

### M4 — Parser (`backend/app/catalog/parser.py`)
- `parse_description(text) -> ParsedFields` pure function: regex price (`₹`/`rs`/`rupees`), unit (`g/kg/ml/l/dozen/pack/pcs/piece`), stock (`N in stock|units|qty`), known-brand list (Amul, Tropicana, Britannia, India Gate, …) else `"Generic"`, category/subcategory keyword match (else General), cleaned `product_name`, raw `description`. Adapted from the existing mock heuristic in `_mocks/index.js` (kept consistent).
- **Verify:** unit-tested directly (no DB).

### M5 — Schemas (`backend/app/schemas/product.py`)
- `ProductCreate`, `ProductUpdate`, `ProductRead` (catalog fields **+** display aliases `id/name/price/stock/category/vendorId` per FR-10), `ProductDescriptionRequest {description_text}`, `CategoryRead`, `SubCategoryRead`. Register in `schemas/__init__.py` (append).

### M6 — Service (`backend/app/services/product_service.py`)
- `list_products`, `create_product`, `create_from_description`, `update_product`, `delete_product`, `delete_by_description`, `list_categories`, `list_subcategories`. Ownership enforced in update/delete/delete-by-description. `ProductValidationError`/`ProductNotFoundError`/`ProductForbiddenError`.

### M7 — Routes + wiring
- `backend/app/api/routes/products.py` — `GET/POST /api/products`, `POST /api/products/from-description`, `PUT/DELETE /api/products/{product_id}`, `POST /api/products/delete-by-description`.
- `backend/app/api/routes/catalog.py` — `GET /api/catalog/categories`, `GET /api/catalog/subcategories`.
- `backend/app/main.py` — enable `docs_url="/docs"`, `openapi_url="/openapi.json"`; `include_router(products...)`, `include_router(catalog...)`. (Only additive edits.)
- **Verify:** `uvicorn` boots; `/docs` lists the new endpoints.

### M8 — Frontend wiring (additive, keep layout)
- `frontend/src/utils/constants.js` — add routes: `productsFromDescription`, `productsDeleteByDescription`, `catalogCategories`, `catalogSubcategories`.
- `frontend/src/services/productService.js` — add `createProductFromDescription(description_text)`, `deleteProductByDescription(description_text)` (keep existing fns).
- `frontend/src/components/products/ProductExtractPanel.jsx` — add an optional `onCreateFromDescription` prop + a primary "Create from description" action beside the existing "Auto-fill fields" (existing prefill path untouched). Voice already flows into the same prompt box.
- `frontend/src/pages/VendorPage.jsx` — pass a handler that calls `createProductFromDescription`, closes the modal, reloads; switch the "Delete by description" row to call `deleteProductByDescription` server-side then reload. Row-level Edit/Delete unchanged. Surface backend errors via the existing error banner.
- `frontend/src/services/_mocks/index.js` — add mock parity handlers for the two new endpoints so `VITE_USE_MOCKS=true` keeps working; document switching to `false` for real backend.
- **Verify:** `npm run lint` clean; `npm run build` succeeds.

### M9 — Tests (`backend/tests/`)
- `test_product_parser.py` — parser unit tests (price/unit/stock/brand/category + missing-price reject).
- `test_products_from_description.py` + `test_products_delete_by_description.py` — service tests against an **in-memory SQLite** session (ORM is portable; fixture creates tables + seeds taxonomy + a vendor, exercises create/delete + ownership). Fixtures local to the test files (shared `conftest.py` untouched).
- **Verify:** `make test` green; `make lint` clean.

### M10 — Audit
- Append session entry to `conversation-history.md`; update `prompts.md`; note decisions in `docs/architecture.md`.

## 3. Risks / notes
- ORM `String(36)` vs migration `UUID` is a pre-existing codebase quirk; 006 follows it rather than "fixing" it (out of scope, would touch 003-owned files).
- Tests run on SQLite for speed/isolation even though runtime is Postgres; only portable column types are used in the ORM, so this is safe.
- `docs_url`/`openapi_url` change in `main.py` is global but additive (enables Swagger; the user asked for it).

## 4. Files created vs modified
- **Created:** 3 models, `0004` migration, `seed_data.py`, `parser.py`, `schemas/product.py`, `product_service.py`, `routes/products.py`, `routes/catalog.py`, 3 test files.
- **Modified (additive only):** `models/__init__.py`, `schemas/__init__.py`, `main.py`, `constants.js`, `productService.js`, `ProductExtractPanel.jsx`, `VendorPage.jsx`, `_mocks/index.js`, `docs/architecture.md`.
- **Off-limits:** `specs/005-catalog/*` (referenced only), 003 auth files, agent module.
