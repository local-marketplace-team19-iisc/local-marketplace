# Architecture Decision Log — Local Marketplace

Living decision log. Each feature appends the decisions it introduced; earlier
entries are never overwritten (Constitution P6). Outranked by
`specs/constitution.md` and `SPEC.md`.

---

## Feature 005 — Catalog (2026-06-20)

**Scope delivered.** The catalog *definition* layer as Pydantic domain models —
`Category`, `SubCategory`, `Product` — with validation and a `UnitType` enum.
No HTTP routes (`/health` remains the only route, SPEC §7). Persistence (SQL
migration) is **deferred** until PostgreSQL is introduced; spec §4 is the schema
contract the future migration must satisfy.

**Module layout.** `backend/app/catalog/` — `enums.py` (`UnitType`), `models.py`
(domain models). Tests in `backend/tests/test_catalog_models.py`.

**Key decisions.**

- **Taxonomy ownership.** `Category` and `SubCategory` are platform-owned and
  predefined (FR-11/FR-12). A `Category` is always top-level (`parent_category_id`
  is null, FR-2); a `SubCategory` belongs to exactly one Category via a non-null
  `parent_category_id` (FR-4).
- **Products are vendor-authored.** A vendor creates a `Product` and assigns it to
  exactly one SubCategory via non-null `subcategory_id` (FR-6/FR-13). No catalog
  uniqueness constraint — duplicates across vendors/locations are allowed (FR-15);
  distinct `product_id`s (UUID) are auto-generated.
- **UnitType enum (FR-7).** `LITER, MILLILITER, KILOGRAM, GRAM, PIECE, PACK, DOZEN`.
  `unit_value` must be a positive Decimal (FR-8).
- **Brand policy (FR-9).** `brand` is required; unbranded/generic/local goods use
  the sentinel `"Generic"`. A Product submitted without a brand is rejected.
- **Pricing — `price_inr` (FR-16..FR-18).** Mandatory Decimal field; currency is
  always INR and **not configurable** (`extra="forbid"` rejects any `currency`
  input, FR-17). Value must be `> 0.00` with **exactly 2 decimal places** (FR-18).
  - *Decided (FR-16, Reading B):* because Products are vendor-authored and
    duplicable, `price_inr` is the **authoritative sale price of that vendor's
    Product row** — not a shared-SKU MSRP. The master SPEC's cheapest-first
    ranking operates across these duplicate rows; the vendor→Product link arrives
    with the later vendor/inventory feature.
  - *Validation note:* the "exactly 2 decimal places" rule is enforced at the
    Pydantic/input layer (checking the raw input's decimal exponent), because a
    future `NUMERIC(_, 2)` column would silently pad `10.1` → `10.10`. Floats are
    rejected to preserve exact money precision. Max precision (total digits) is
    unspecified and will be set when the SQL migration is written.

- **Referential FK existence is deferred.** Models enforce presence/type/value;
  checking that `parent_category_id` / `subcategory_id` point at *existing* rows is
  a persistence-layer concern introduced with the database.
