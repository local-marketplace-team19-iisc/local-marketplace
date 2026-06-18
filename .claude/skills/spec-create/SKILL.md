---
name: spec-create
description: Scaffold a new Spec-Driven-Development feature under specs/<NNN-slug>/ — creates spec.md, plan.md, prompts.md, conversation-history.md, sets the .active_feature pointer, and follows specs/constitution.md. Use when the user wants to start or create a new feature spec, e.g. "/spec-create 001-db-schema" or "create a spec/feature for ...".
---

# spec-create

Bootstraps one governed feature folder for this repo's SDD workflow. **Spec/plan
artifacts only** — it never writes implementation files (Constitution P1).

## Input

A single feature id `<NNN-slug>`: a 3-digit number + lowercase kebab slug, e.g.
`001-db-schema`, `002-vendor-onboarding`. Product features start at `001`
(`000-app-scaffold` already exists). If the user gave a name but no number, propose
the next free `NNN` and confirm.

## Authority (read first, resolve conflicts upward)

1. `specs/constitution.md` — supreme. Note especially P1 (dry-run), P2 (no guesses),
   P3 (audit trail), P6 (idempotent writes), P7 (.active_feature context binding).
2. `SPEC.md` — master spec; §4 defines the per-feature folder layout.

## Procedure

1. **Validate the id.** Must match `^\d{3}-[a-z0-9]+(-[a-z0-9]+)*$`. If it already
   exists under `specs/`, do not clobber it — report and stop (P6).
2. **Scaffold** by running the bundled script from the repo root:

   ```bash
   python3 .claude/skills/spec-create/scaffold_feature.py <NNN-slug>
   ```

   It is idempotent: it creates only missing files, never overwrites existing ones,
   and writes `<NNN-slug>` into the gitignored `.active_feature` (P7). It creates:
   - `specs/<NNN-slug>/spec.md` — the architectural contract (lowercase `spec.md`
     per SPEC §4 / Constitution P3) with the required sections:
     **User Scenarios & Edge Cases · Functional Requirements & Decisions ·
     Success / Acceptance Criteria · DB Schema Entities ·
     Requirement Completeness / Definition of Done**.
   - `specs/<NNN-slug>/plan.md` — dry-run, seeded **AWAITING APPROVAL** (P1).
   - `specs/<NNN-slug>/prompts.md` — chronological log + ranked recurring
     interactions with `[SKILL CANDIDATE]` flagging (P3).
   - `specs/<NNN-slug>/conversation-history.md` — append-only session log (P3, P7),
     pre-seeded with the scaffolding session.
3. **Fill the spec with the user.** Replace every `[NEEDS CLARIFICATION]` in
   `spec.md` and `plan.md` by asking the user — never guess (P2). Leave any genuine
   unknown explicitly marked rather than inventing an answer.
4. **Do NOT implement.** Per P1, no implementation file may be created or modified
   until the user reviews and approves `plan.md`. Stop after the spec/plan are ready.
5. **Close out (P3 & P7).** Before ending the session, append a timestamped entry to
   `specs/<NNN-slug>/conversation-history.md` (context/goal, decisions + reasoning,
   unknowns raised/resolved, files altered) and log the prompt in `prompts.md`.

## Guardrails

- Touch only the new feature's slice; files owned by other features are off-limits (P6).
- Never edit `CLAUDE.md` (human-owned, PR-only — P5) or the constitution as part of
  scaffolding.
- `.active_feature` is gitignored (P7); the four feature artifacts are committed (P3).
