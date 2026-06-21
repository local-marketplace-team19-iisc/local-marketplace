---
name: review-spec
description: Ruthlessly stress-test a feature's spec.md for missing information, logical contradictions, unresolved architectural forks, and unhandled edge cases — read-only. Produces a severity-ranked report of blockers and architectural decisions to confirm the blueprint is 100% implementation-ready. Never writes code. Use when the user wants to validate/review/audit a spec, e.g. "/review-spec", "review the 001-db-schema spec", "is this spec ready to implement?".
---

# review-spec

Adversarial, **read-only** review of a feature's `spec.md`. The goal is to find every
gap before an engineer hits it: missing information, logical contradictions,
unresolved architectural forks, and unhandled edge cases. **Stress-test the blueprint
— do not build it.**

This skill writes **nothing**: no code, no edits to `spec.md`, no scaffolding. Its only
output is the review report it returns to the user. (If the user later asks to apply
fixes, that is a separate, explicit action — not part of this review.)

## Input

Optional feature id `<NNN-slug>`. If omitted, resolve the active feature from the
gitignored `.active_feature` file at the repo root (Constitution P7). **Fail closed:**
if `.active_feature` is missing/empty or names a directory that does not exist under
`specs/`, and no id was given, halt and ask the user which feature to review — never
guess.

## Authority (read first, resolve conflicts upward)

1. `specs/constitution.md` — supreme. Especially **P2** (specs must be precise,
   complete, unambiguous; unknowns are `[NEEDS CLARIFICATION]`, never guesses) and
   **P1** (no implementation before an approved `plan.md`).
2. `SPEC.md` — master product spec + target stack/constraints. Every feature spec is
   outranked by it; the review MUST check the feature spec against it.
3. `specs/<feature>/spec.md` — the document under review.
4. `docs/architecture.md` — living decision log; prior decisions a spec must not contradict.

## Procedure

1. **Bind context.** Resolve the feature (input or `.active_feature`), then read its
   `spec.md` in full, plus `SPEC.md`, `specs/constitution.md`, and (if present)
   `docs/architecture.md`. Also skim the feature's `plan.md` / `conversation-history.md`
   for decisions already made.
2. **Sweep each review axis** (below) across every section of the spec.
3. **Cross-check against the master `SPEC.md`** — every product promise the feature
   touches (e.g. currency precision, ranking rules, proximity, auth, latency NFRs)
   must be satisfiable by the schema/contract as written.
4. **Classify and rank** every finding by severity. Be ruthless but precise: each
   finding must name the exact location and explain *why* it blocks implementation.
5. **Return the report** in the output format below. Do not modify any file.

## Review axes (the stress-test)

- **Missing information** — columns/fields/types/constraints/indexes referenced in
  scenarios or acceptance criteria but never defined; product promises in `SPEC.md`
  (price precision, ranking, proximity radius, auth) with no schema/field to back them;
  unpinned choices (model dims, SRID, index type, driver, versions).
- **Logical contradictions** — a field that is both `Nullable` and `ON DELETE RESTRICT`;
  entity counts that disagree with the entity list; a relationship naming a table that
  isn't defined; an acceptance criterion that conflicts with a stated constraint.
- **Unresolved architectural forks** — "X or Y" left undecided (async vs sync driver,
  ENUM vs lookup table, cascade vs restrict). Each fork is a `[NEEDS CLARIFICATION]`
  the spec must resolve before code.
- **Unhandled edge cases** — concurrency/race conditions, partial-failure/rollback,
  duplicate/retry, deletion cascades, orphan rows, empty/boundary inputs, idempotency.
  For each scenario, ask "what does the DB/contract do when this goes wrong?"
- **Scope creep / altitude** — logic that belongs to a *different* feature (e.g.
  application transaction orchestration inside a pure schema feature). Flag boundary
  ambiguity explicitly.
- **Governance (Constitution P2/P3)** — unresolved `[NEEDS CLARIFICATION]` markers; a
  "Definition of Done" that claims completeness while real unknowns remain; broken /
  empty requirement tables; duplicate section numbering; missing audit artifacts.

## Output format

Return a single report — no file writes:

1. **Verdict** — one line: `READY` or `NOT READY`, plus the single most important reason.
2. **🔴 Critical blockers** — must be fixed before any implementation. Each: location
   (`spec.md` section / entity / line), what's wrong, why it blocks, and the concrete
   decision needed.
3. **🟠 Ambiguities & contradictions** — same structure; resolve before coding.
4. **🟡 Structural / governance defects** — table/heading/marker issues, P2/P3 hygiene.
5. **Architectural decisions to confirm** — the open forks, each stated as a crisp
   either/or with a recommended default and its trade-off, so the user can decide fast.

Frame findings as `[NEEDS CLARIFICATION: ...]` candidates where the resolution is the
user's to make. Recommend, don't guess (P2).

## Guardrails

- **Read-only.** Never create or modify `spec.md`, code, or any file during a review.
- Never edit `CLAUDE.md` (human-owned, PR-only — P5) or the constitution.
- Do not begin implementation; a review never satisfies P1's dry-run gate.
- If asked to *fix* the findings afterward, treat that as a separate request and edit
  only the current feature's `spec.md` slice (P6) — still no code before `plan.md` approval.
