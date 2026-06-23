---
name: dry-run-spec
description: Mentally simulate execution of a feature's spec.md and plan.md to find silent failures, broken wiring, and implementation blockers before any code is written. Traces each plan milestone step-by-step to verify every path exists, every prerequisite is provisioned, every spec acceptance criterion is covered, and no step silently succeeds while producing a wrong result. Use when the user asks "will this actually work?", "dry-run the spec/plan", "check for silent failures", "simulate execution of the feature", "validate the plan against the spec", or wants pre-implementation confidence that the feature will work end-to-end.
metadata:
  author: s0m0avx
arguments:
  - "[NNN-slug] - optional, feature id (e.g. 001-db-schema); resolves from .active_feature if omitted"
sample-prompts:
  - "dry-run-spec 001-db-schema"
  - "will this feature actually work? dry run it"
  - "check for silent failures in the spec and plan"
  - "simulate execution of the current feature"
---

# dry-run-spec

**Read-only** simulation of a feature's `plan.md` against its `spec.md`. Goal: find every
silent failure, broken wiring, missing prerequisite, and spec promise that the plan does not
actually deliver — before a single implementation file is touched.

This skill writes **nothing**. Its only output is the simulation report.

## Input

Optional feature id `<NNN-slug>`. If omitted, resolve from `.active_feature` at the repo
root (Constitution P7). **Fail closed:** if `.active_feature` is missing, empty, or names
a non-existent directory, halt and ask — never guess.

## Authority (read first)

1. `specs/constitution.md` — supreme; P1 (no code before approved plan.md), P2 (no guesses).
2. `SPEC.md` — master product spec; stack constraints and NFRs are ground truth.
3. `specs/<feature>/spec.md` — the acceptance criteria and schema contract being simulated.
4. `specs/<feature>/plan.md` — the execution sequence being traced.
5. `docs/architecture.md` — prior decisions the plan must not contradict.

## Procedure

1. **Bind context.** Read `spec.md`, `plan.md`, `SPEC.md`, `specs/constitution.md`, and
   `docs/architecture.md` in full.
2. **Run structural & programmatic integrity checks** (see axes below) on both files
   before any simulation. Integrity failures are reported separately and are always
   🔴 — a structurally broken document cannot be reliably simulated.
3. **Build the execution model.** Extract every file path, service, env var, and artifact
   each plan step creates or consumes. Build a dependency graph: what each step needs vs.
   what prior steps have produced.
4. **Simulate each milestone in order.** For every step, run all seven simulation axes
   (below) and record failures.
5. **Map spec → plan coverage.** For every acceptance criterion in `spec.md §3` and every
   entity constraint in `spec.md §4`, confirm at least one plan step implements it. Flag
   unmapped criteria as silent omissions.
6. **Map plan → spec grounding.** For every plan step, confirm it traces to a spec
   requirement. Flag orphaned steps as scope creep.
7. **Rank and return the report.** Classify findings by severity. Do not modify any file.

## Structural & programmatic integrity axes

Run these mechanically on the raw document text before any semantic simulation.

**spec.md structural checks**
- All required sections present: §1 Scenarios, §2 FR table, §3 Acceptance Criteria, §4 Entity matrix, §5 System Constraints, §6 DoD.
- FR table: no blank decision cells; no cell containing meta-instructions instead of a decision.
- Entity matrix: every row has non-empty Key fields, Relationships, and Notes cells.
- No unresolved `[NEEDS CLARIFICATION]` markers anywhere in the document.
- No stale HTML comments (`<!-- BLOCKED: ... -->` or similar).
- DoD checklist: all items use `- [ ]` format.

**plan.md structural checks**
- Every milestone contains at least one `- [ ]` step; a prose-only milestone with no checkboxes is incomplete.
- All checkboxes use `- [ ]` format — bare `[ ]` (missing the `- ` prefix) will not render and signals an unreviewed draft.
- No `[NEEDS CLARIFICATION]` markers remain.
- STATUS block (`AWAITING APPROVAL` / `APPROVED`) is present at the bottom.

**Programmatic cross-reference checks (spec.md ↔ plan.md)**
- **Entity count consistency:** count the entity rows in spec.md §4; verify this matches the count stated in spec.md §3 ("All N models: …"). A mismatch means either the entity matrix or the acceptance criterion is wrong.
- **FK target validity:** every FK target named in spec.md §4 (e.g. `FK → categories.id`) must match an entity defined in §4. A reference to an undefined table is a broken constraint that will fail at migration time.
- **Constraint coverage:** every `CHECK`, `UNIQUE`, index, identity sequence, and FK delete rule declared in spec.md §3/§4 must appear in plan.md Milestone 2 constraint checklist. Missing entries will be silently absent from the migration.
- **Test coverage:** every FK delete rule (`ON DELETE CASCADE / RESTRICT / SET NULL`) and every `CHECK` constraint declared in spec.md §4 must have a corresponding assertion in plan.md Milestone 4. Missing test assertions mean the constraint will never be verified.
- **Path consistency:** every file path that appears in spec.md (model paths, migration dir, init SQL path) must exactly match the path used in the corresponding plan.md step. A single-character mismatch is a silent wiring error.

## Simulation axes

- **Step ordering** — does the step consume an artifact (file, running service, migration
  state) that a prior step has not yet produced? Flag the exact missing predecessor.

- **Path & file existence** — every file path referenced in a step must either already
  exist in the repo or be created by an earlier step in the same plan. Check: model import
  paths in `env.py`, Dockerfile `COPY` sources, init SQL mount targets, `alembic.ini`
  `script_location`, session factory URL construction.

- **Prerequisite availability** — env vars, running containers, installed packages, and
  superuser DB access assumed by a step must be explicitly provisioned by an earlier step.
  Flag any implicit dependency (e.g. "alembic upgrade head" before container is up).

- **Silent failure modes** — steps that will execute without error but produce a wrong
  result. Examples: `alembic revision --autogenerate` succeeds but silently omits a table
  because `target_metadata` points to the wrong `Base`; `CREATE EXTENSION IF NOT EXISTS`
  silently no-ops if the DB user lacks superuser; an HNSW index defined on a Nullable
  column with no `WHERE` predicate silently excludes NULL rows from all searches; a
  `server_default` set only in SQLAlchemy but missing from the Alembic-generated DDL.

- **Spec-to-plan coverage** — every `spec.md §3` acceptance criterion and every `spec.md
  §4` column/constraint/index must map to a concrete plan step. Unmapped items are silent
  omissions: the migration will run clean but the schema will be wrong.

- **Dependency wiring** — verify that components reference each other correctly: `env.py`
  imports `Base.metadata` from the right module; `session.py` constructs the `asyncpg`
  URL from the correct env var names; `docker-compose.yml` mounts the init SQL into
  `/docker-entrypoint-initdb.d/`; the Alembic `script_location` matches the actual
  migrations directory on disk.

- **Reversibility** — does `alembic downgrade base` undo every object the upgrade creates?
  Check that custom types (GEOGRAPHY, VECTOR), extensions, and indexes are explicitly
  dropped in `downgrade()` — Alembic autogenerate does not handle these automatically.

## Output format

Return a single report — no file writes:

1. **Verdict** — one line: `SIMULATION PASSES` or `SIMULATION FAILS`, plus the single
   most critical failure reason. If structural integrity checks fail, verdict is always
   `SIMULATION FAILS — document integrity broken` regardless of simulation results.
2. **🔴 Structural & programmatic integrity failures** — document-level defects found
   before simulation. Each: file (`spec.md` or `plan.md`), exact location (section /
   table row / line), what is wrong, and why it blocks reliable simulation. Report these
   first; they must be fixed before simulation findings are meaningful.
3. **🔴 Silent failures** — steps that execute without error but produce a wrong result.
   Each: milestone + step, the failure mode, what the engineer will observe vs. what they
   expect, and the fix.
3. **🔴 Broken wiring** — a step consumes an artifact not yet produced, or a component
   references the wrong path/symbol. Each: which step, what's missing, which prior step
   must produce it.
4. **🟠 Missing prerequisites** — implicit env vars, services, or permissions not
   explicitly provisioned. Each: what's assumed, where it's assumed, what step must
   provision it.
5. **🟠 Spec coverage gaps** — acceptance criteria or entity constraints in `spec.md`
   with no corresponding plan step. Each: the exact criterion, why it will be silently
   omitted, and which milestone should cover it.
6. **🟡 Ordering issues** — steps that are sequenced incorrectly but won't error
   immediately (e.g. migration generated before models are finalized).
7. **🟡 Reversibility gaps** — upgrade objects not dropped in `downgrade()`.

## Guardrails

- **Read-only.** Never create or modify any file during simulation.
- Never edit `CLAUDE.md` (human-owned, PR-only — Constitution P5) or `constitution.md`.
- Do not begin implementation; this simulation never satisfies the P1 dry-run gate.
- If asked to fix findings afterward, treat that as a separate request scoped to the
  current feature's `plan.md` or `spec.md` slice only (P6) — still no code before
  plan.md approval.
