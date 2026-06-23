---
title: "Feature 006: Vendor Product Management"
status: draft
created: 2026-06-23
---

# Feature 006: Vendor Product Management — Specification

> Architectural contract for feature `006-vendor-product-management` (Constitution P3).
> Mark every unknown `[NEEDS CLARIFICATION: ...]` — never guess (Constitution P2).
> Outranked by `specs/constitution.md` and the master `SPEC.md`.
> **Schema authority:** the catalog schema is owned by `specs/005-catalog/spec.md`.
> This feature does **not** redefine it — it persists it and adds the runtime
> workflow + the four operational fields 005 explicitly deferred (vendor link,
> stock, timestamps).

## Feature Overview

**Problem statement.** Feature 005 defined the catalog *schema* (Category →
SubCategory → Product) but deferred persistence and all lifecycle/ownership
behaviour. The vendor-facing frontend (Feature 004) renders an "add product from
a description" panel and a "delete by description" box, but there is no backend
to (a) persist a product, (b) extract catalog fields from free text, or (c)
delete a vendor's own product by description. This feature implements that
workflow end-to-end against PostgreSQL.

**Why this feature exists.** It is the first feature to *persist* the 005 catalog
and to give a vendor create/list/update/delete over **their own** products, driven
by typed or spoken natural-language descriptions.

**Scope — Included**

- SQLAlchemy models + Alembic migration for `categories`, `subcategories`, `products`.
- A seeded, deterministic catalog taxonomy (categories + subcategories).
- A deterministic (non-LLM) description → catalog-fields parser.
- Product REST routes (list / create / create-from-description / update / delete /
  delete-by-description) scoped to the authenticated vendor for writes.
- Catalog read routes (categories, subcategories).
- Frontend wiring: `productService.js` + `VendorPage`/`ProductExtractPanel` so a
  product is created from a description and shown in the vendor list; delete by
  typed/spoken description.
- Swagger/OpenAPI enabled.

**Scope — Excluded**

- Semantic/vector search, embeddings, distance/ranking (later features).
- Orders, cart, inventory decrement on purchase.
- Category/SubCategory authoring by vendors (005 FR-11/FR-12: platform-owned).
- Image/OCR extraction backend (the existing `/api/extract/product` stays mock-only).
- Editing the 005 schema contract.

## 1. User Scenarios & Edge Cases

1. **Create from description.**
   - *Given* an authenticated vendor on the Manage-products page
   - *When* they type or speak product details into "Describe the product" and submit
   - *Then* the backend parses catalog fields, persists a `products` row owned by that
     vendor, and the vendor list reloads showing the new product.
   - **Edge cases:** no price found → reject (price is mandatory, 005 FR-16); no
     recognizable category → assign the seeded **General** subcategory; no brand →
     `"Generic"`; no unit → `PIECE`/`1`; no stock → `0`.

2. **Delete by description.**
   - *Given* a vendor with existing products
   - *When* they type or speak a description into "Delete by description" and submit
   - *Then* the backend matches **only that vendor's** products by name/brand/description
     keywords, deletes the single best match, and the list reloads without it.
   - **Edge cases:** no match → `404` with a clear message; match owned by another
     vendor → never selected (ownership filter); ambiguous (tie) → delete the
     highest-scoring single match, deterministic by score then `created_at`.

3. **List / update / delete by id.** Existing row-level Edit/Delete keep working
   against `PUT`/`DELETE /api/products/{id}`, vendor-scoped.

## 2. Functional Requirements & Decisions

| ID | Requirement (MUST/SHOULD) | Decision taken & rationale |
| :-- | :-- | :-- |
| FR-1 | Persist `categories`, `subcategories`, `products` per the 005 schema contract (005 §4), on PostgreSQL. | 005 deferred persistence; user chose Postgres (runtime) — matches docker-compose + existing Alembic chain. |
| FR-2 | `products` MUST add four operational fields beyond 005: `vendor_id` (FK → `vendors.id`, NOT NULL), `stock_quantity` (int ≥ 0, default 0), `created_at`, `updated_at` (timestamps). | Required to scope ownership (delete-by-description) and display stock; 005 FR-14/FR-15 deferred these to "the vendor/inventory onboarding feature" — that is this feature. |
| FR-3 | All 005 product rules MUST hold: `brand` NOT NULL (sentinel `"Generic"`), `unit_type` ∈ UnitType, `unit_value` > 0, `price_inr` > 0.00 with exactly 2 dp, `subcategory_id` NOT NULL → existing SubCategory. | Re-uses 005 validation (do not weaken the contract). |
| FR-4 | A deterministic parser MUST extract from free text: `product_name`; `brand` (default `"Generic"`); `price_inr` (mandatory, normalized to exactly 2 dp); `unit_type`+`unit_value` (default `PIECE`/`1`); `stock_quantity` (default `0`); category/subcategory when recognizable; `description` (the raw text). | User-specified; no LLM ("deterministic parser first"). |
| FR-5 | When no category/subcategory is recognized, the product MUST be assigned the seeded **General → General** subcategory (keeps 005 `subcategory_id` NOT NULL). | User decision (2026-06-23). |
| FR-6 | If the parser cannot find a `price_inr`, create MUST be rejected with a clear `400`. | 005 FR-16: price is mandatory; cannot be defaulted. |
| FR-7 | A seeded taxonomy MUST exist, derived from the 005 examples (Dairy→Milk, Beverages→Juices, Bakery→Bread, Staples→Rice) plus the frontend `PRODUCT_CATEGORIES`, each with a `General` subcategory, plus a top-level `General → General` fallback. | User decision (2026-06-23). Single source in `catalog/seed_data.py`. |
| FR-8 | Product write routes (`POST`, `PUT`, `DELETE`, `from-description`, `delete-by-description`) MUST require an authenticated **vendor** and operate only on that vendor's rows. Read routes (`GET /api/products`, `/api/catalog/*`) MAY be unauthenticated. | Re-uses 003 JWT (`Authorization: Bearer`); mirrors mock-layer 401/403. |
| FR-9 | `delete-by-description` MUST score the current vendor's products by name/brand/description keyword overlap and delete the single best match; no match → `404`. | Mirrors the existing frontend `findToDelete` heuristic, moved server-side and ownership-scoped. |
| FR-10 | `GET /api/products` responses MUST carry frontend-display aliases (`id`, `name`, `price`, `stock`, `category`, `vendorId`) **and** the raw catalog fields, so `VendorPage` renders unchanged. | Field map (user-specified): name↔product_name, price↔price_inr, stock↔stock_quantity, category↔(sub)category name, vendorId↔vendor_id. |
| FR-11 | Swagger MUST be enabled: `docs_url="/docs"`, `openapi_url="/openapi.json"`. | User-specified; only main.py FastAPI() kwargs change. |
| FR-12 | New routers MUST be wired into `backend/app/main.py` under `/api/products` and `/api/catalog`; no existing route changed. | Constitution P6 (idempotent, scoped). |

## 3. Success / Acceptance Criteria

- [ ] Backend starts without errors against PostgreSQL; `alembic upgrade head` applies `0004`.
- [ ] Swagger reachable at `http://localhost:8000/docs`; OpenAPI at `/openapi.json`.
- [ ] A vendor can create a product from a typed description; row persisted in `products`.
- [ ] Voice input (existing `VoiceButton`) feeds the same create path.
- [ ] Vendor list reloads and shows the new product (unchanged styling/layout).
- [ ] A vendor can delete by typed **or** spoken description; row removed from DB.
- [ ] Delete only ever targets the calling vendor's own rows.
- [ ] Create with no parseable price is rejected with a clear error.
- [ ] `GET /api/catalog/categories` and `/subcategories` return the seeded taxonomy.
- [ ] `make test` green (new tests for create-from-description and delete-by-description); `ruff` clean.

## 4. DB Schema Entities

005 §4 remains the contract for Category/SubCategory/Product fields. This feature
**persists** them and adds the FR-2 operational columns on `products`.

| Entity | Key fields (type) | Notes |
| :-- | :-- | :-- |
| categories | `category_id` (UUID PK), `category_name` (str, unique), `parent_category_id` (UUID, null) | 005 FR-1/FR-2; always top-level. |
| subcategories | `subcategory_id` (UUID PK), `subcategory_name` (str), `parent_category_id` (UUID FK→categories, NOT NULL), `subcategory_description` (str) | 005 FR-3/FR-4. |
| products | 005 fields: `product_id` (UUID PK), `subcategory_id` (UUID FK→subcategories, NOT NULL), `product_name` (str), `brand` (str, default `"Generic"`), `description` (text), `unit_type` (Enum UnitType), `unit_value` (Numeric(10,3) >0), `price_inr` (Numeric(10,2) >0) **+ 006:** `vendor_id` (UUID FK→vendors, NOT NULL), `stock_quantity` (int ≥0, default 0), `created_at`, `updated_at` (timestamps) | No uniqueness constraint (005 FR-15). Indexes on `vendor_id`, `subcategory_id`. |

> ID columns follow the existing codebase pattern: Alembic emits PostgreSQL `UUID`
> (matching `users`/`vendors`), while ORM models declare `String(36)` (matching
> `User`/`Vendor`) — this feature does not change that established convention.

## 5. Requirement Completeness / Definition of Done

- [ ] No unresolved `[NEEDS CLARIFICATION]` (P2). *(none — 4 forks resolved 2026-06-23.)*
- [ ] `plan.md` written and **user-approved** before any implementation (P1).
- [ ] All FRs (§2) covered by passing tests where testable.
- [ ] All Acceptance Criteria (§3) met and verified.
- [ ] DB entities (§4) migrated (`0004`); schema matches 005 + FR-2.
- [ ] `make test` green and `make lint` clean.
- [ ] Audit trail committed: `spec.md`, `plan.md`, `prompts.md`, `conversation-history.md`.
- [ ] `docs/architecture.md` updated with decisions this feature introduced.
