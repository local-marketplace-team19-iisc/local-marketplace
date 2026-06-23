# Feature 006 — Prompts Log

Chronological log of LLM prompts for this feature (Constitution P3).

## 2026-06-23

1. **Implementation request (verbatim intent).** "Implement the vendor product
   workflow using the existing frontend design as reference." Use
   `specs/005-catalog/spec.md` as the schema contract; do not rewrite it. Read
   the listed backend/frontend files first. Backend tasks: models + Alembic
   migration for categories/subcategories/products; Pydantic schemas; product
   routes (list/create/from-description/update/delete/delete-by-description);
   catalog routes (categories/subcategories); wire routers; enable Swagger;
   deterministic parser; vendor-scoped delete-by-description; tests. Frontend
   tasks: keep VendorPage design; add `createProductFromDescription` +
   `deleteProductByDescription`; connect ProductExtractPanel/VendorPage; keep
   voice input; map display↔catalog fields; show backend errors. "Ask me before
   making unclear schema or UX decisions."

2. **Clarifying questions (AskUserQuestion) + answers.**
   - Table creation on default SQLite vs Postgres-only Alembic chain → **"use
     PostgreSQL db"**. Resolution: target Postgres; tables via Alembic `0004`.
   - Unknown category (005 `subcategory_id` NOT NULL) → **seed a `General`
     fallback subcategory**.
   - Parser defaults for missing fields → **brand=Generic, unit=PIECE/1,
     stock=0** (missing price → reject).
   - Seed taxonomy → **derive from 005 examples + frontend PRODUCT_CATEGORIES**.

3. **Plan approval gate.** `plan.md` presented for approval before any
   implementation file is written (P1). → **"Approved"** (2026-06-23).

4. **Implementation.** Built M1–M10 (models, migration, seed data, parser,
   schemas, service, routes, Swagger wiring, frontend wiring, tests). Verified:
   13 new tests pass, ruff clean, frontend lint/build pass.

## Recurring interactions

_None at 3+ occurrences yet. Watch for: "map frontend display fields to catalog
fields" and "scope writes to the current vendor" — recurring shapes that may
become `[SKILL CANDIDATE]` if they repeat across features._
