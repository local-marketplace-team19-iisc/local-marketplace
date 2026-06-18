#!/usr/bin/env python3
"""Scaffold a new SDD feature folder under specs/<NNN-slug>/.

Constitution-compliant (specs/constitution.md):
  P1 Dry-run  : seeds plan.md as an *unapproved* dry-run template.
  P2 Specs    : seeds spec.md with [NEEDS CLARIFICATION] markers, never guesses.
  P3 Audit    : creates spec.md + prompts.md + conversation-history.md.
  P6 Idempotent: never overwrites an existing artifact; only fills missing files.
  P7 Context  : writes <NNN-slug> into the gitignored .active_feature pointer.

Usage:  python3 .claude/skills/spec-create/scaffold_feature.py <NNN-slug>
Example: python3 .claude/skills/spec-create/scaffold_feature.py 001-db-schema
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

FEATURE_RE = re.compile(r"^\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*$")


def find_repo_root() -> Path:
    """Walk up from CWD until specs/constitution.md is found."""
    for d in (Path.cwd(), *Path.cwd().parents):
        if (d / "specs" / "constitution.md").is_file():
            return d
    sys.exit("ERROR: not inside the repo — specs/constitution.md not found above CWD.")


def title_of(slug: str) -> str:
    num, _, rest = slug.partition("-")
    words = rest.replace("-", " ").title()
    return f"Feature {num}: {words}"


def render(template: str, *, slug: str, title: str, num: str, today: str) -> str:
    return (
        template.replace("{{SLUG}}", slug)
        .replace("{{TITLE}}", title)
        .replace("{{NUM}}", num)
        .replace("{{DATE}}", today)
    )


SPEC_TMPL = """---
title: {{TITLE}}
feature: {{SLUG}}
status: draft
created: {{DATE}}
---

# {{TITLE}} — Specification

> Architectural contract for feature `{{SLUG}}` (Constitution P3).
> Mark every unknown `[NEEDS CLARIFICATION: ...]` — never guess (Constitution P2).
> Outranked by `specs/constitution.md` and the master `SPEC.md`.

## 1. User Scenarios & Edge Cases

Primary scenarios (Given / When / Then), each with the edge cases it must handle.

1. **Scenario:** [NEEDS CLARIFICATION: describe the primary user journey]
   - *Given* …
   - *When* …
   - *Then* …
   - **Edge cases:** [NEEDS CLARIFICATION: empty input, concurrency, not-found, limits, …]

## 2. Functional Requirements & Decisions

Each requirement is testable; each records the decision taken (and why) so the
"how" is auditable. Open points stay `[NEEDS CLARIFICATION]`.

| ID | Requirement (MUST/SHOULD) | Decision taken & rationale |
| :-- | :-- | :-- |
| FR-1 | [NEEDS CLARIFICATION] | [NEEDS CLARIFICATION] |

## 3. Success Criteria / Acceptance Criteria

Objective, verifiable criteria that mark this feature "done & correct".

- [ ] [NEEDS CLARIFICATION: measurable acceptance criterion]

## 4. DB Schema Entities

Entities introduced/changed by this feature (tables, key columns, types,
relationships, indexes/extensions). Migrations live in `backend/migrations/`.

| Entity | Key fields (type) | Relationships | Notes (indexes / constraints) |
| :-- | :-- | :-- | :-- |
| [NEEDS CLARIFICATION] | | | |

## 5. Requirement Completeness / Definition of Done

This feature is DONE only when **all** hold:

- [ ] No unresolved `[NEEDS CLARIFICATION]` markers remain (Constitution P2).
- [ ] `plan.md` was written and **user-approved** before any implementation (P1).
- [ ] All Functional Requirements (§2) have passing tests.
- [ ] All Success/Acceptance Criteria (§3) are met and verified.
- [ ] DB entities (§4) are migrated; schema matches the spec.
- [ ] `make test` green and `make lint` clean.
- [ ] Audit trail current: `spec.md`, `plan.md`, `prompts.md`,
      `conversation-history.md` all committed (P3).
- [ ] `docs/architecture.md` updated with any decision this feature introduced.
"""

PLAN_TMPL = """# Plan — {{TITLE}} (Dry-Run)

> **Iron-Clad Rule (Constitution P1 / SPEC §8):** this dry-run MUST be reviewed and
> **approved by the user** before any implementation file is created or modified.

## Scope

[NEEDS CLARIFICATION: what this feature delivers; what is explicitly out of scope]

## Files to CREATE

| Path | Purpose |
| :-- | :-- |
| | |

## Files to MODIFY (append/merge only — Constitution P6)

| Path | Change |
| :-- | :-- |
| | |

## Files explicitly NOT touched

- `CLAUDE.md` — human-owned; AI forbidden to modify (Constitution P5).
- `specs/constitution.md`, `SPEC.md` — governing docs; not changed by execution.
- Any file owned by another feature (Constitution P6).

## Key execution decisions

1. [NEEDS CLARIFICATION]

## Architectural risks

- **R1** — [NEEDS CLARIFICATION]

## Verification steps (post-implementation)

1. [NEEDS CLARIFICATION]

---
**STATUS: AWAITING APPROVAL.** No implementation file will be created or modified
until this plan is approved by the user.
"""

PROMPTS_TMPL = """# Prompts — {{TITLE}}

Chronological log of LLM prompts for this feature (Constitution P3).

## Chronological log

1. **"/spec-create {{SLUG}}"** — scaffolded the feature folder and audit artifacts.

## Recurring interactions

Repeated prompts (verbatim or by intent), ranked by frequency. Any interaction
recurring **≥3 times** is flagged `[SKILL CANDIDATE]` for promotion into a reusable
skill (Constitution P3).

| Count | Interaction (by intent) | Source prompts | Flag |
| :-- | :-- | :-- | :-- |
| 1 | Scaffold a new feature spec | #1 | — |
"""

HISTORY_TMPL = """# Conversation History — {{TITLE}}

Append-only, cumulative log of every working session on this feature
(Constitution P3 & P7). Earlier entries are NEVER overwritten or truncated.
Each entry: context/goal · decisions + reasoning · edge cases / unknowns ·
`[NEEDS CLARIFICATION]` raised or resolved · files altered.

---

## {{DATE}} — Session 1: Feature scaffolding

- **Context / goal:** Initialise feature `{{SLUG}}` via `/spec-create`.
- **Decisions:** Created `specs/{{SLUG}}/` with `spec.md`, `plan.md`, `prompts.md`,
  `conversation-history.md`; set `.active_feature` → `{{SLUG}}` (P7).
- **Unknowns raised:** spec.md & plan.md seeded with `[NEEDS CLARIFICATION]` markers
  to be resolved with the user before any implementation (P1, P2).
- **Files altered:** new feature folder + `.active_feature`.
"""

FILES = {
    "spec.md": SPEC_TMPL,
    "plan.md": PLAN_TMPL,
    "prompts.md": PROMPTS_TMPL,
    "conversation-history.md": HISTORY_TMPL,
}


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit("Usage: scaffold_feature.py <NNN-slug>   e.g. 001-db-schema")
    slug = sys.argv[1].strip()
    if not FEATURE_RE.match(slug):
        sys.exit(
            f"ERROR: '{slug}' is not a valid feature id. "
            "Expected NNN-slug, lowercase, e.g. 001-db-schema."
        )

    root = find_repo_root()
    num = slug.split("-")[0]
    title = title_of(slug)
    today = date.today().isoformat()
    feat_dir = root / "specs" / slug

    feat_dir.mkdir(parents=True, exist_ok=True)

    created, skipped = [], []
    for name, tmpl in FILES.items():
        path = feat_dir / name
        if path.exists():
            skipped.append(name)
            continue
        path.write_text(render(tmpl, slug=slug, title=title, num=num, today=today))
        created.append(name)

    # P7: .active_feature is the single source of truth for the active feature.
    (root / ".active_feature").write_text(slug + "\n")

    print(f"Feature : {slug}  ({title})")
    print(f"Folder  : specs/{slug}/")
    print(f"Created : {', '.join(created) or '(none)'}")
    if skipped:
        print(f"Skipped : {', '.join(skipped)}  (already existed — P6 idempotency)")
    print(f".active_feature -> {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
