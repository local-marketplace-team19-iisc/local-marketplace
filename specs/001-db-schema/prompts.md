# Prompts — Feature 001: Db Schema

Chronological log of LLM prompts for this feature (Constitution P3).

## Chronological log

1. **"/spec-create 001-db-schema"** — scaffolded the feature folder and audit artifacts.

### Session 2 — 2026-06-21
2. **"validate 001-db-schema spec and flag missing information or ambiguity"** — full validation vs constitution + master SPEC.
3. **"Add the price (NUMERIC(10,2)) with B-Tree index on price"** — `inventory.price` for cheapest-first sort.
4. **"add quantity (INT) CHECK (quantity > 0) default 1 to cart_lines and order_lines; add price to cart_lines"** — line quantities + (later reverted) cart price.
5. **"Add quantity and purchase_price to finalize the frozen snapshot pattern"** — `order_lines.purchase_price`.
6. **"cart is volatile intent … remove pricing from cart_line"** — dropped `cart_lines.price`.
7. **"resolve #8: Remove Nullable, enforce NOT NULL with ON DELETE RESTRICT"** — `order_lines.inventory_id`.
8. **"Update point 9: strictly require asyncpg + AsyncSession"** — resolved the driver fork.
9. **"point 10: keep self-referential table, drop the strict ENUM"** — `categories`.
10. **"point 12: deleted product should silently vanish from carts"** — `cart_lines.inventory_id` ON DELETE CASCADE.
11. **"wire up inventory.product_id cascade to finish the chain"** — completed product→inventory→cart_lines cascade.
12. **"Update point 13: add created_at on orders"** — write-once receipt timestamp.
13. **"create a skill named review-spec"** — authored the read-only spec auditor skill.
14. **"Run review-spec on 001-db-schema"** — re-audited the spec.
15. **"define inventory.stock_quantity (INTEGER NOT NULL default 0, CHECK >= 0); update SPEC.md to email instead of mobile OTP"** — core column + auth model.
16. **"Define password_hash column"** — added; corrected encrypt/decrypt → one-way salted hash.
17. **"Apply a strict UNIQUE constraint to orders.order_number"**.
18. **"make vector search functional: name/description, pin bge-small-en-v1.5, HNSW + vector_cosine_ops"** — `products`.
19. **"add the model pin to §5"** — echoed pinned model into System Constraints.
20. **"Declare order_number as INTEGER GENERATED ALWAYS AS IDENTITY"**.
21. **"vendors.location → GEOGRAPHY(Point, 4326)"**.
22. **"apply ON DELETE RESTRICT to products.category_id → categories.id"** (made explicit).
23. **"un-check the false 'no NEEDS CLARIFICATION' DoD box — anti-pattern while plan.md is placeholders"**.
24. **"strip all application-level transactional orchestration from this schema feature"** — Scenario 2 rewrite.
25. **"conversation-history.md and prompts.md are not being updated"** — this audit-trail catch-up (P3/P7).

### Session 3 — 2026-06-21
26. **"run the review-spec again on 001-db-schema"** — second adversarial audit (plan.md now drafted; new gaps surfaced).
27. **"add both operational tracking columns to the carts table"** — declared `carts.created_at` + `carts.updated_at`.

## Recurring interactions

Repeated prompts (verbatim or by intent), ranked by frequency. Any interaction
recurring **≥3 times** is flagged `[SKILL CANDIDATE]` for promotion into a reusable
skill (Constitution P3).

| Count | Interaction (by intent) | Source prompts | Flag |
| :-- | :-- | :-- | :-- |
| ~18 | Resolve one review finding by adding/adjusting a column, constraint, index, or FK delete-rule in `spec.md` + a matching §3 acceptance criterion | #3–#12, #15–#22, #24 | **[SKILL CANDIDATE]** — `apply-spec-refinement` (atomic schema edit + criterion + audit append) |
| 2 | Validate / adversarially review the spec for gaps & ambiguities | #2, #14 | **[REALIZED]** — promoted to the `review-spec` skill (#13) |
| 1 | Keep the audit trail current (history + prompts) | #25 | — |
| 1 | Scaffold a new feature spec | #1 | — |
