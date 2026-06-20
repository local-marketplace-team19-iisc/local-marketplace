# Plan — Feature 005: Catalog (Dry-Run)

> **Iron-Clad Rule (Constitution P1 / SPEC §8):** this dry-run MUST be reviewed and
> **approved by the user** before any implementation file is created or modified.

## Scope

**Delivers:** the catalog *definition* layer for item onboarding — the domain
models, the standardized `UnitType` enum, **product pricing (`price_inr`)**, the
product validation rules, and the catalog governance rules (ownership, assignment,
fixed INR currency) per `spec.md`. Persistence (SQL migration) is **deferred**
until PostgreSQL is introduced; the DB schema (spec §4) remains the contract the
models must satisfy. Entity deletion / lifecycle is **out of scope** (descoped by
user; spec FR-14).

**Explicitly out of scope (per spec):** inventory, vendor onboarding,
authentication, orders, cart, semantic search, embeddings, distance calculations,
ranking logic. No HTTP routes are added — `/health` remains the only route
(SPEC §7). Location-scoped duplicate prevention is owned by the (out-of-scope)
onboarding/inventory feature; the catalog adds no uniqueness constraint (FR-15).

## Files to CREATE

| Path | Purpose |
| :-- | :-- |
| `backend/app/catalog/__init__.py` | Package marker for the catalog domain module. |
| `backend/app/catalog/enums.py` | `UnitType` enum: `LITER, MILLILITER, KILOGRAM, GRAM, PIECE, PACK, DOZEN` (FR-7). |
| `backend/app/catalog/models.py` | Pydantic domain models `Category`, `SubCategory`, `Product` + validation (FR-1..FR-9, FR-13, FR-16..FR-18) incl. `subcategory_id` FK field, `brand` sentinel default, positive-Decimal `unit_value`, and **`price_inr`** (Decimal, INR, mandatory, > 0.00, exactly 2 decimal places). |
| `backend/tests/test_catalog_models.py` | Unit tests for validation, relationships, brand sentinel, and **`price_inr`** (mandatory; accept `10.00`/`65.50`/`999.99`; reject `10`/`10.1`/`0.00`/`-5.00`) — covers acceptance criteria §3. |

> Module path `backend/app/catalog/` mirrors the existing `backend/app/...` layout.

## Files DEFERRED (not created in this feature)

| Path | Reason |
| :-- | :-- |
| `backend/migrations/0001_catalog.sql` | DDL for `category`, `subcategory`, `product` deferred until PostgreSQL is introduced (per resolved persistence decision). Schema contract preserved in spec §4. |

## Files to MODIFY (append/merge only — Constitution P6)

| Path | Change |
| :-- | :-- |
| `docs/architecture.md` | Append the catalog schema + governance decisions introduced by this feature (DoD §5). |

## Files explicitly NOT touched

- `CLAUDE.md` — human-owned; AI forbidden to modify (Constitution P5).
- `specs/constitution.md`, `SPEC.md` — governing docs; not changed by execution.
- `backend/app/main.py`, `backend/app/api/routes/*` — no new routes in this feature (SPEC §7).
- Any file owned by another feature (Constitution P6).

## Key execution decisions (resolved with user)

1. **Definition-only feature.** Delivered as the schema/validation layer
   (Pydantic models + enum), not as API endpoints.
2. **Product→SubCategory link.** Add `subcategory_id` (UUID, FK → SubCategory,
   NOT NULL) to Product to enforce "exactly one subcategory" (FR-6).
3. **UnitType enum.** `LITER, MILLILITER, KILOGRAM, GRAM, PIECE, PACK, DOZEN` (FR-7).
4. **Brand policy.** `brand` required; unbranded/generic/local goods use the
   sentinel `"Generic"` (FR-9).
5. **Deletion out of scope.** Entity deletion / lifecycle (incl. soft delete) is
   descoped from 005 and deferred to a future feature (FR-14). No `deleted_at`.
6. **Ownership.** Categories/SubCategories are predefined & platform-owned;
   vendors only create Products and assign to a predefined SubCategory (FR-11..13).
7. **No uniqueness at catalog layer.** Duplicates allowed; location-scoped dedup
   deferred to the onboarding/inventory feature (FR-15).
8. **Persistence deferred.** Pydantic models now; SQL migration later.
9. **Pricing (`price_inr`).** Mandatory Decimal field, currency hard-coded to INR
   and non-configurable (FR-16/FR-17). Validation: `> 0.00` AND **exactly 2 decimal
   places** (FR-18). The "exactly 2 dp" rule must be enforced at the **Pydantic/input
   layer** — a future `NUMERIC(_, 2)` column would silently pad `10.1` → `10.10` and
   accept it, so the decimal-place count is checked on the raw input before
   normalization. Max precision (total digits) is unspecified by the business
   decision and will be set when the migration is written.

## Architectural risks

- **RESOLVED (FR-16) — pricing model.** Decided 2026-06-20 (Reading B): Products are
  vendor-authored (FR-13) and duplicable across vendors/locations (FR-15), so
  `price_inr` is the **authoritative sale price** of that vendor's Product row, and
  cheapest-first ranking works across duplicate rows. The vendor→Product link is
  added by the later vendor/inventory feature. No FR rework required; no open
  pricing risk remains.

## Verification steps (post-implementation)

1. `make test` green — including `test_catalog_models.py` covering each
   acceptance criterion in spec §3 (accepted **and** rejected cases).
2. `make lint` clean (ruff).
3. Domain models match the schema contract in spec §4 (fields, types, FK,
   sentinel default, `price_inr`).
4. Each rule (FR-2, FR-4, FR-6, FR-7, FR-8, FR-9, FR-13, FR-15, FR-16, FR-17,
   FR-18) has an asserting test — including `price_inr` mandatory, INR-only,
   `> 0.00`, and the exactly-2-decimal-places accept/reject matrix.

## Blockers

**None.** No open `[NEEDS CLARIFICATION]` markers remain — FR-16 was resolved
2026-06-20 (Reading B); R1–R5 remain resolved (Constitution P2 satisfied).

---
**STATUS: APPROVED (2026-06-20) — CLEARED FOR IMPLEMENTATION.** The pricing-revised
dry-run was approved by the user on 2026-06-20 (Constitution P1) and the last open
clarification (FR-16) is resolved (Constitution P2). Implementation of the catalog
definition layer — including `price_inr` (FR-16..FR-18) — may now begin per the
"Files to CREATE" table above.
