# Conversation History — Feature 005: Catalog

Append-only, cumulative log of every working session on this feature
(Constitution P3 & P7). Earlier entries are NEVER overwritten or truncated.
Each entry: context/goal · decisions + reasoning · edge cases / unknowns ·
`[NEEDS CLARIFICATION]` raised or resolved · files altered.

---

## 2026-06-19 — Session 1: Feature scaffolding

- **Context / goal:** Initialise feature `005-catalog` via `/spec-create`.
- **Decisions:** Created `specs/005-catalog/` with `spec.md`, `plan.md`, `prompts.md`,
  `conversation-history.md`; set `.active_feature` → `005-catalog` (P7).
- **Unknowns raised:** spec.md & plan.md seeded with `[NEEDS CLARIFICATION]` markers
  to be resolved with the user before any implementation (P1, P2).
- **Files altered:** new feature folder + `.active_feature`.

---

## 2026-06-19 — Session 2: Populate spec.md from source PDF

- **Context / goal:** Fill `spec.md` with the content of the provided
  "Feature Specification - Item Onboarding Catalog" PDF, without changing the
  existing template's rules or format (frontmatter, constitutional blockquote,
  numbered sections + tables preserved).
- **Decisions:** Mapped PDF content into the existing sections — Feature
  Overview (problem/why/scope in & out), §1 scenarios + edge cases + hierarchy
  examples, §2 functional-requirements table (FR-1..FR-14) capturing the
  approved Category/SubCategory/Product schema and constraints, §3 acceptance
  criteria, §4 DB entities. Kept §5 Definition of Done unchanged. Did not
  generate plan.md or implementation code (P1).
- **Unknowns raised `[NEEDS CLARIFICATION]`:** complete UnitType enum values
  (only LITER given); required vs optional Product fields; missing-brand /
  generic / local-unbranded handling; duplicate-product definition & handling;
  category & subcategory ownership rules; product assignment rules beyond the
  one-subcategory constraint; soft- vs hard-delete behavior; and notably the
  **SubCategory FK on Product** — required by the "exactly one subcategory"
  constraint but absent from the approved Product schema.
- **Files altered:** `specs/005-catalog/spec.md`.

---

## 2026-06-19 — Session 3: Generate plan.md (dry-run) + prompts.md

- **Context / goal:** Produce the dry-run `plan.md` and update `prompts.md` for
  feature 005, from the now-populated `spec.md`.
- **Decisions:** Scoped 005 as a **definition-only** feature (domain models +
  `UnitType` enum + validation + DB schema; no HTTP routes — `/health` stays the
  only route per SPEC §7). Proposed creating `backend/app/catalog/` (`enums.py`,
  `models.py`), `backend/migrations/0001_catalog.sql`, and
  `backend/tests/test_catalog_models.py`; modify only `docs/architecture.md`
  (append). Relationship rules enforced via non-null FKs + Pydantic parity.
- **Unknowns / blockers carried forward:** R1 missing Product→SubCategory FK
  (FR-6), R2 UnitType enum values (FR-7), R3 soft/hard delete (FR-14), R4
  required-vs-optional fields (FR-9), R5 duplicate handling. Added an open
  execution decision on persistence timing (ship migration now vs. defer to
  PostgreSQL). Plan kept **AWAITING APPROVAL**; no implementation started (P1).
- **Files altered:** `specs/005-catalog/plan.md`, `specs/005-catalog/prompts.md`.

---

## 2026-06-19 — Session 4: Resolve clarifications (R1–R5) + descope deletion

- **Context / goal:** Walk through and resolve the open `[NEEDS CLARIFICATION]`
  markers so spec.md/plan.md can become marker-free (P2).
- **Decisions (resolved with user):**
  - **R1 Product→SubCategory link:** add `subcategory_id` (UUID, FK → SubCategory,
    NOT NULL) to Product (FR-6). (User's first answer "product_id" was clarified —
    that is the Product's own PK and cannot reference a subcategory.)
  - **R2 UnitType enum:** `LITER, MILLILITER, KILOGRAM, GRAM, PIECE, PACK, DOZEN` (FR-7).
  - **R4 Brand:** required; unbranded/generic/local goods use sentinel `"Generic"` (FR-9).
  - **R5 Duplicates:** no catalog-level uniqueness; location-scoped dedup is out of
    scope (owned by onboarding/inventory) since location/vendor is excluded (FR-15).
  - **Ownership (FR-11..13):** derived from the "predefined categories/subcategories"
    constraint — Categories/SubCategories are platform-owned; vendors only create
    Products and assign each to one predefined SubCategory.
  - **Persistence:** Pydantic models + enum now; SQL migration deferred.
  - **R3 Delete behavior — reversed mid-session.** Initially chose soft delete;
    resolving the parent-with-active-children sub-question, the user instead chose to
    **remove soft delete**. Since hard delete was not elected, entity deletion /
    lifecycle is **descoped** from 005 and deferred to a future feature (FR-14,
    added to Excluded scope) — a deliberate scope decision, not a guess.
- **Edge cases / unknowns:** none left open; verified no live `[NEEDS CLARIFICATION]`
  markers remain in spec.md §1–§5 or plan.md.
- **Files altered:** `specs/005-catalog/spec.md`, `specs/005-catalog/plan.md`.

---

## 2026-06-20 — Session 5: Introduce catalog product pricing (`price_inr`)

- **Context / goal:** Update the active feature spec (`005-catalog`) to add catalog
  product pricing per a business decision: a new mandatory `Product.price_inr` field
  (Decimal, currency INR, exactly 2 decimal places, > 0.00, currency non-configurable).
- **Decisions made:**
  - **Scope change:** moved pricing from *Excluded* into *Included* scope; the catalog
    now defines product pricing. (Reverses the earlier exclusion.)
  - **Schema:** added `price_inr` (Decimal, scale 2, NOT NULL, > 0.00, INR) to the
    Product schema (FR-5), the required-fields list (FR-9), §1 scenario fields, the
    hierarchy examples, and the §4 DB schema entity row.
  - **Validation/governance:** added FR-16 (mandatory `price_inr`, Decimal/INR/2 dp),
    FR-17 (currency always INR, not configurable), FR-18 (value > 0.00 AND exactly
    2 decimal places; reject `10`, `10.1`, `0.00`, `-5.00`; accept `10.00`, `65.50`,
    `999.99`). Added matching §3 acceptance criteria. Extended FR-8 validation list.
- **Reasoning:** Follows the explicit business decision and the master SPEC's stated
  "₹ currency with 2 decimal precision". Kept currency hard-coded to INR (no config)
  to honor single-currency governance. Illustrative `price_inr` values were added to
  the example entries and explicitly labelled illustrative (the source spec had none),
  so they are not mistaken for fixed requirements.
- **Edge cases / unknowns — `[NEEDS CLARIFICATION]` raised:** The master `SPEC.md`
  (which outranks this feature spec) models price as a **per-vendor listing attribute**
  ("catalog product + price + stock") to enable cheapest-first ranking across vendors.
  Placing a single `price_inr` on the shared catalog Product implies one global price.
  Raised a `[NEEDS CLARIFICATION]` on FR-16: is catalog `price_inr` the single
  authoritative sale price, or a base/MSRP that vendors override at listing time?
  Per Constitution P2 this was flagged rather than guessed. (This reopens the §5 DoD
  "no unresolved markers" gate until resolved.)
- **Files altered:** `specs/005-catalog/spec.md`, `specs/005-catalog/prompts.md`,
  `specs/005-catalog/conversation-history.md`. No implementation code; no files
  outside the active feature (Constitution P1, P5, P6).

---

## 2026-06-20 — Session 6: Validate spec + refresh plan.md for pricing

- **Context / goal:** Validate the pricing-updated `spec.md` against the constitution,
  then bring the dry-run `plan.md` in sync with the new `price_inr` scope.
- **Decisions made:**
  - **Validation outcome:** spec is internally consistent (FR ↔ AC ↔ DB all trace);
    one intentional `[NEEDS CLARIFICATION]` (FR-16) keeps the feature short of DoD §5.
  - **plan.md updated:** added `price_inr` to scope, to `models.py` and
    `test_catalog_models.py` purposes, to verification steps (FR-16..FR-18 test
    matrix), and a new execution decision (#9) for pricing.
  - **Corrected stale claims in plan.md:** the prior "no open markers / risks none
    open" statements were updated to record the live FR-16 risk and blocker.
- **Edge cases / unknowns:** Flagged that "exactly 2 decimal places" (reject `10.1`)
  is a **Pydantic/input-layer** rule — a `NUMERIC(_, 2)` column would pad `10.1` →
  `10.10` and accept it. Noted that `price_inr` max precision (total digits) is
  unspecified and will be set at migration time. FR-16 clarification remains **open**.
- **Files altered:** `specs/005-catalog/plan.md`,
  `specs/005-catalog/conversation-history.md`.

---

## 2026-06-20 — Session 7: Approve dry-run + resolve FR-16 (pricing model)

- **Context / goal:** User approved the pricing-revised `plan.md` and asked to
  resolve the open FR-16 pricing-model clarification.
- **Decisions made:**
  - **plan.md approved** (Constitution P1) — `STATUS: APPROVED (2026-06-20)`.
  - **FR-16 resolved — Reading B (authoritative, vendor-authored price).** Because
    Products are vendor-authored (FR-13) and duplicable across vendors/locations
    (FR-15), `price_inr` is the **authoritative sale price of that vendor's Product
    row**, not a shared-SKU reference/MSRP. The master SPEC's cheapest-first ranking
    operates across these duplicate Product rows; the vendor→Product link is added by
    the later vendor/inventory feature. No FR rework required.
- **Reasoning:** Reading B is the interpretation already implied by the approved
  FR-13/FR-15; Reading A (shared SKU + per-listing price) would have contradicted
  them and required revising those FRs. Recommended B; user confirmed.
- **Edge cases / unknowns:** **FR-16 marker cleared** — no `[NEEDS CLARIFICATION]`
  markers remain in spec.md or plan.md (P2 satisfied). Implementation is now
  unblocked. `price_inr` max precision (total digits) is still to be set when the
  SQL migration is written (deferred, not blocking).
- **Files altered:** `specs/005-catalog/spec.md`, `specs/005-catalog/plan.md`,
  `specs/005-catalog/prompts.md`, `specs/005-catalog/conversation-history.md`.

---

## 2026-06-20 — Session 8: Implement catalog definition layer (per approved plan)

- **Context / goal:** First implementation session for 005 — execute the approved,
  marker-free plan (P1/P2 both satisfied). Build the catalog definition layer.
- **Decisions made / how implemented:**
  - **Created** `backend/app/catalog/__init__.py`, `backend/app/catalog/enums.py`
    (`UnitType` enum, FR-7), `backend/app/catalog/models.py` (Pydantic `Category`,
    `SubCategory`, `Product`), and `backend/tests/test_catalog_models.py`.
  - **`price_inr` (FR-16..FR-18):** mandatory Decimal; `> 0.00` and exactly 2
    decimal places validated via a `mode="before"` field validator that inspects the
    raw input's Decimal exponent (so `10.1`/`10`/`0.00`/`-5.00` are rejected and
    `10.00`/`65.50`/`999.99` accepted). Floats rejected to preserve money precision.
  - **Currency non-configurability (FR-17):** models use `extra="forbid"`, so there
    is no `currency` field and passing one raises — INR is fixed in code.
  - **Brand (FR-9):** `brand` required (no default), so a Product without a brand is
    rejected; `"Generic"` is passed explicitly for unbranded goods. (Chosen to honor
    acceptance criterion §3 "submitted without a brand is rejected"; the §4 "default
    sentinel" wording is read as the sentinel *value*, not a programmatic default.)
  - **FK existence deferred:** models enforce presence/type/value; checking that
    `parent_category_id`/`subcategory_id` reference *existing* rows is a
    persistence-layer concern (no datastore in this feature).
  - **Appended** feature 005 decisions to `docs/architecture.md` (was empty;
    initialized with a header + the 005 entry).
- **Verification:** `python -m pytest` → **25 passed**; `ruff check .` → clean.
  Ticked the now-satisfied §3 acceptance criteria and §5 DoD items in spec.md;
  left DB-migration (deferred) and "audit committed" (commit pending) unchecked.
- **Edge cases / unknowns:** `price_inr` max precision (total digits) still
  unspecified — to be fixed when the SQL migration is written. No new
  `[NEEDS CLARIFICATION]` raised.
- **Files altered:** `backend/app/catalog/__init__.py`,
  `backend/app/catalog/enums.py`, `backend/app/catalog/models.py`,
  `backend/tests/test_catalog_models.py`, `docs/architecture.md`,
  `specs/005-catalog/spec.md`, `specs/005-catalog/prompts.md`,
  `specs/005-catalog/conversation-history.md`.
