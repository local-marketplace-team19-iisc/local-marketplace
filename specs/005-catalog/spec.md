---
title: "Feature 005: Catalog"
status: draft
created: 2026-06-19
---

# Feature 005: Catalog — Specification

> Architectural contract for feature `005-catalog` (Constitution P3).
> Mark every unknown `[NEEDS CLARIFICATION: ...]` — never guess (Constitution P2).
> Outranked by `specs/constitution.md` and the master `SPEC.md`.

## Feature Overview

**Problem statement.** The marketplace has no shared, deterministic catalog
structure, so vendors lack a predefined taxonomy and product schema to onboard
products against. Without it, product data is inconsistent and cannot be
validated or organized.

**Why this feature exists.** It defines the marketplace catalog structure that
vendors use when onboarding products — the categories, subcategories, product
schema, validation rules, and catalog governance rules. It is the structural
foundation that later onboarding/search features depend on.

**Scope — Included**

- Category definition
- Subcategory definition
- Product schema definition
- Product pricing (`price_inr`, INR)
- Product validation rules
- Catalog governance rules

**Scope — Excluded**

- Inventory
- Vendor onboarding
- Authentication
- Orders
- Cart
- Semantic search implementation
- Embeddings
- Distance calculations
- Ranking logic
- Entity deletion / lifecycle management (deferred to a future feature)

## 1. User Scenarios & Edge Cases

Primary scenarios (Given / When / Then), each with the edge cases it must handle.

1. **Scenario: Vendor onboards a product under a predefined category and subcategory.**
   - *Given* a predefined Category and one of its SubCategories exist in the catalog taxonomy
   - *When* a vendor onboards a Product and assigns it to exactly one SubCategory via `subcategory_id`
   - *Then* the Product is registered with its schema fields (`product_name`,
     `brand`, `description`, `unit_type`, `unit_value`, `price_inr`) linked to that single SubCategory,
     and the catalog hierarchy (Category → SubCategory → Product) is deterministic.
   - **Edge cases:**
     - *Missing brand* — brand is **required**; a product submitted without a brand is rejected.
       Generic/local/unbranded goods are recorded with the reserved sentinel `brand = "Generic"`.
     - *Generic products* — products with no distinguishing brand identity use `brand = "Generic"`.
     - *Local / unbranded products* — same handling: `brand = "Generic"` (no separate field).
     - *Duplicate products* — the catalog applies **no uniqueness constraint**. The same
       product may legitimately exist multiple times across **different locations**;
       duplicates from the **same location** are not permitted. Because location/vendor is
       **excluded** from this feature, the location-scoped duplicate rule is owned and
       enforced by the vendor/inventory onboarding feature — see FR-15.

**Hierarchy / Example Catalog Entries** (Category → SubCategory → Product):

- Dairy → Milk → Amul *Full Cream Milk* — `unit_type` LITER, `unit_value` 1, `price_inr` 65.50
- Beverages → Juices → Tropicana *Orange Juice* — `unit_type` MILLILITER, `unit_value` 1000, `price_inr` 110.00
- Bakery → Bread → Britannia *Whole Wheat Bread* — `unit_type` GRAM, `unit_value` 400, `price_inr` 45.00
- Staples → Rice → India Gate *Basmati Rice* — `unit_type` KILOGRAM, `unit_value` 5, `price_inr` 545.00

> The first example is fixed by the source spec; the additional three are illustrative,
> consistent with the approved schema and the UnitType enum (FR-7). All `price_inr`
> values shown are illustrative additions (the source spec carried no price); each
> satisfies the FR-16..FR-18 format (INR, > 0.00, exactly 2 decimal places).

## 2. Functional Requirements & Decisions

Each requirement is testable; each records the decision taken (and why) so the
"how" is auditable. Open points stay `[NEEDS CLARIFICATION]`.

| ID | Requirement (MUST/SHOULD) | Decision taken & rationale |
| :-- | :-- | :-- |
| FR-1 | Catalog MUST define a **Category** with `category_id` (UUID), `category_name` (String), `parent_category_id`. | Per approved catalog schema. |
| FR-2 | A Category's `parent_category_id` MUST always be `null` (categories are top-level). | Source schema: "always null for parent categories". |
| FR-3 | Catalog MUST define a **SubCategory** with `subcategory_id` (UUID), `subcategory_name` (String), `parent_category_id` (UUID), `subcategory_description` (String). | Per approved catalog schema. |
| FR-4 | A SubCategory MUST belong to **exactly one** Category, referenced by `parent_category_id` (NOT NULL, existing Category). | Constraint: "A subcategory belongs to exactly one category." |
| FR-5 | Catalog MUST define a **Product** with `product_id` (UUID), `product_name` (String), `brand` (String), `description` (String), `unit_type` (Enum), `unit_value` (Decimal), `price_inr` (Decimal, INR, 2 dp). | Per approved catalog schema; `price_inr` added by the catalog product pricing business decision (FR-16). |
| FR-6 | A Product MUST belong to **exactly one** SubCategory via `subcategory_id` (UUID, FK → SubCategory, NOT NULL). | Resolves the source gap (no link field in the approved Product schema); `subcategory_id` added to record the owning subcategory. |
| FR-7 | `unit_type` MUST be one of the **UnitType** enum: `LITER`, `MILLILITER`, `KILOGRAM`, `GRAM`, `PIECE`, `PACK`, `DOZEN`. | Standardized grocery unit set; covers volume, weight, and count. |
| FR-8 | Product fields MUST validate: required string fields non-empty; `unit_value` a positive Decimal; `unit_type` ∈ UnitType; `subcategory_id` references an existing SubCategory; `price_inr` a positive Decimal with exactly 2 decimal places (see FR-16..FR-18). | Derived from schema field types + relationship + pricing rules. |
| FR-9 | **Required** Product fields: `product_id`, `subcategory_id`, `product_name`, `brand`, `description`, `unit_type`, `unit_value`, `price_inr`. `brand` is required and uses the sentinel `"Generic"` when unbranded. No Product field is optional. | Brand policy resolved with user; sentinel keeps brand non-null for generic/local goods; `price_inr` mandatory per FR-16. |
| FR-10 | Category hierarchy MUST be deterministic. | Constraint: "Category hierarchy is deterministic." |
| FR-11 | **Category ownership:** Categories are predefined and platform/admin-owned; vendors MUST NOT create, rename, or delete Categories. | Derived from constraint "vendors onboard under *predefined* categories". |
| FR-12 | **Subcategory ownership:** SubCategories are predefined and platform/admin-owned; vendors MUST NOT create, rename, or delete SubCategories. | Same derivation as FR-11. |
| FR-13 | **Product assignment:** A vendor creates a Product and assigns it to exactly one predefined SubCategory; assignment to a non-existent SubCategory is rejected. | Constraint + FR-6. |
| FR-14 | Entity **deletion / lifecycle management** (delete behavior for Category, SubCategory, Product) is **out of scope** for this feature and deferred to a future feature. | Descoped by user decision; feature 005 covers catalog *definition* only. |
| FR-15 | The catalog MUST NOT enforce product uniqueness. Location-scoped duplicate prevention is **out of scope** (owned by the vendor/inventory onboarding feature). | Duplicates allowed across locations; location/vendor excluded from 005. |
| FR-16 | Product MUST include a **`price_inr`** field — type Decimal, currency INR, **exactly 2 decimal places** (e.g. `10.00`, `65.50`, `999.99`). `price_inr` is **mandatory**; no Product may exist without it. | Catalog product pricing business decision (2026-06-20). **Resolved 2026-06-20 (Reading B):** Products are vendor-authored (FR-13) and duplicable across vendors/locations (FR-15), so `price_inr` is the **authoritative sale price of that vendor's Product row** — not a shared-SKU reference/MSRP. The master SPEC's cheapest-first ranking operates across these duplicate Product rows. The vendor→Product link itself arrives with the future vendor/inventory feature (vendor/location is excluded from 005); `price_inr` rides on the Product until then. No FR rework required. |
| FR-17 | `price_inr` currency MUST always be Indian Rupees (**INR**) and MUST NOT be configurable. | Single-currency platform governance; no multi-currency support in the catalog. |
| FR-18 | `price_inr` MUST validate: value **> 0.00** AND **exactly 2 decimal places**. Reject values with no decimals (`10`), fewer than 2 decimals (`10.1`), zero (`0.00`), or negative (`-5.00`). Accept `10.00`, `65.50`, `999.99`. | Derived from the business rules and the provided valid/invalid examples. |

## 3. Success Criteria / Acceptance Criteria

Objective, verifiable criteria that mark this feature "done & correct".

- [x] A Category can be created with `parent_category_id = null`; a Category with a non-null parent is rejected.
- [x] A SubCategory references exactly one existing Category via `parent_category_id`; a SubCategory referencing a missing Category is rejected. *(non-null parent enforced at model layer; FK-existence deferred to persistence.)*
- [x] A Product is assigned to exactly one SubCategory via `subcategory_id`; a Product with no `subcategory_id`, or one referencing a missing SubCategory, is rejected. *(presence enforced; FK-existence deferred to persistence.)*
- [x] A Product with an invalid `unit_type` (outside the UnitType enum) is rejected; a non-positive or non-Decimal `unit_value` is rejected.
- [x] A Product submitted without a `brand` is rejected; an unbranded product stored with `brand = "Generic"` is accepted.
- [x] A Product submitted without a `price_inr` is rejected (price is mandatory, FR-16).
- [x] A `price_inr` of `10.00`, `65.50`, or `999.99` is accepted; `10`, `10.1`, `0.00`, and `-5.00` are rejected (FR-18).
- [x] `price_inr` is always interpreted as INR; the currency cannot be configured or overridden (FR-17).
- [x] The hierarchy "Dairy → Milk → Amul Full Cream Milk (LITER, 1)" can be represented end-to-end.
- [x] Two identical product definitions are both accepted by the catalog (no uniqueness constraint enforced at this layer).
- [x] The Category → SubCategory → Product hierarchy resolves deterministically for any catalog entry.

## 4. DB Schema Entities

Entities introduced/changed by this feature (tables, key columns, types,
relationships, indexes/extensions). The SQL migration is **deferred** until
PostgreSQL is introduced (see plan.md); this section is the schema contract that
both the Pydantic models (this feature) and the future migration must satisfy.

| Entity | Key fields (type) | Relationships | Notes (indexes / constraints) |
| :-- | :-- | :-- | :-- |
| Category | `category_id` (UUID, PK), `category_name` (String), `parent_category_id` (null) | Parent of SubCategory (one → many) | `parent_category_id` always `null` (FR-2). |
| SubCategory | `subcategory_id` (UUID, PK), `subcategory_name` (String), `parent_category_id` (UUID, FK → Category), `subcategory_description` (String) | Belongs to exactly one Category; parent of Product | `parent_category_id` references an existing Category (FR-4). |
| Product | `product_id` (UUID, PK), `subcategory_id` (UUID, FK → SubCategory, NOT NULL), `product_name` (String), `brand` (String, default sentinel `"Generic"`), `description` (String), `unit_type` (Enum: UnitType), `unit_value` (Decimal, > 0), `price_inr` (Decimal scale 2, NOT NULL, > 0.00) | Belongs to exactly one SubCategory | `unit_type` ∈ UnitType (FR-7); `subcategory_id` references an existing SubCategory (FR-6/FR-13); no uniqueness constraint (FR-15); `price_inr` NOT NULL, exactly scale 2, > 0.00, currency INR fixed/non-configurable (FR-16..FR-18). |

## 5. Requirement Completeness / Definition of Done

This feature is DONE only when **all** hold:

- [x] No unresolved `[NEEDS CLARIFICATION]` markers remain (Constitution P2).
- [x] `plan.md` was written and **user-approved** before any implementation (P1).
- [x] All Functional Requirements (§2) have passing tests.
- [x] All Success/Acceptance Criteria (§3) are met and verified.
- [ ] DB entities (§4) are migrated; schema matches the spec. *(Deferred until PostgreSQL is introduced; §4 remains the contract.)*
- [x] `make test` green and `make lint` clean. *(25 passed; ruff clean — 2026-06-20.)*
- [ ] Audit trail current: `spec.md`, `plan.md`, `prompts.md`,
      `conversation-history.md` all committed (P3). *(Updated; commit pending.)*
- [x] `docs/architecture.md` updated with any decision this feature introduced.
