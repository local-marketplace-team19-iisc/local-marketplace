# Prompts — Feature 005: Catalog

Chronological log of LLM prompts for this feature (Constitution P3).

## Chronological log

1. **"/spec-create 005-catalog"** — scaffolded the feature folder and audit artifacts.
2. **"I provided Feature Specification - Item Onboarding Catalog [PDF]; populate the
   PDF contents into spec.md without changing its existing rules/format."** — filled
   spec.md from the source PDF, mapping into the existing template sections.
3. **"Generate the plan.md and prompt.md."** — produced the dry-run plan.md and
   logged this session's prompts in prompts.md.
4. **"yes" (resolve clarifications) + clarification answers** — resolved R1–R5
   via guided Q&A; descoped entity deletion/lifecycle (FR-14) per user decision;
   removed all `[NEEDS CLARIFICATION]` markers from spec.md and plan.md.
5. **"Update the active feature specification to introduce catalog product pricing
   (`price_inr`: Decimal, INR, 2 dp, mandatory, > 0.00, currency non-configurable)."**
   — moved pricing into scope; added `price_inr` to the Product schema, examples,
   validation (FR-16..FR-18), acceptance criteria, and DB schema; flagged the
   catalog-vs-per-vendor pricing tension as `[NEEDS CLARIFICATION]` (FR-16) per P2.
6. **"validate the spec" → "update plan.md to cover pricing" → "approved" +
   FR-16 = Reading B.** — validated spec consistency; refreshed `plan.md` for the
   pricing scope; recorded user approval of the dry-run; resolved FR-16 as the
   **authoritative vendor-authored price** (Reading B), clearing the last marker
   and unblocking implementation (P1, P2).
7. **"yes, implement them per the approved plan."** — implemented the catalog
   definition layer: `backend/app/catalog/{enums.py,models.py}` + tests; appended
   feature 005 decisions to `docs/architecture.md`. `make test` green (25),
   `make lint` clean.

## Recurring interactions

Repeated prompts (verbatim or by intent), ranked by frequency. Any interaction
recurring **≥3 times** is flagged `[SKILL CANDIDATE]` for promotion into a reusable
skill (Constitution P3).

| Count | Interaction (by intent) | Source prompts | Flag |
| :-- | :-- | :-- | :-- |
| 1 | Scaffold a new feature spec | #1 | — |
| 1 | Populate spec.md from a provided source document | #2 | — |
| 1 | Generate plan.md + prompts.md for the active feature | #3 | — |
| 1 | Update spec.md to introduce/modify a Product field from a business decision | #5 | — |
