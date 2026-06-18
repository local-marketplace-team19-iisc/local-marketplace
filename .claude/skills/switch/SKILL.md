---
name: switch
description: Switch the active SDD feature — auto-saves and commits the current feature's specs/<NNN-slug>/ artifacts as a new version, then points .active_feature at the target. Stops with an error if the named feature does not exist (typo guard). Use when the user wants to switch/change to another feature, e.g. "/switch 002-vendor-onboarding".
---

# switch

Moves the active feature pointer from the current feature to another **existing**
one, checkpointing the current feature's work first so nothing is lost.

## Input

A single existing feature id `<NNN-slug>` (e.g. `002-vendor-onboarding`). The target
**must already exist** under `specs/`. If it doesn't (typo or never scaffolded), the
switch is refused — use `/spec-create` to create a new feature instead.

## Authority

`specs/constitution.md` is supreme — note **P3** (audit trail: feature artifacts are
versioned/committed) and **P7** (`.active_feature` binds context; it is gitignored).

## Procedure

1. **Close out the current feature (P3 / P7).** Before switching, append a
   timestamped session-closing entry to the *current* feature's
   `specs/<current>/conversation-history.md` (context/goal, decisions + reasoning,
   unknowns raised/resolved, files altered). Read `.active_feature` to learn which
   feature is current; if it is missing/empty there is nothing to close out.
2. **Switch + auto-commit** by running the bundled script from the repo root:

   ```bash
   python3 .claude/skills/switch/switch_feature.py <NNN-slug>
   ```

   The script:
   - **Refuses unknown targets** — if `specs/<NNN-slug>/` does not exist it prints
     "no such feature" plus the available list and aborts (typo guard).
   - **Auto-saves the current feature** — `git add -A` of `specs/<current>/` only,
     then, if anything changed, an auto commit (the new version). Scope is limited to
     the current feature's slice, so unrelated working-tree changes are never swept in.
   - **Updates `.active_feature`** to the target (the pointer stays gitignored — P7).
3. **Report** the from→to move, the checkpoint commit hash (if one was made), and the
   new active feature.

## Guardrails

- Never switch to a non-existent feature — stop and tell the user (catches typos).
- Only the current feature's folder is committed; do not stage other features' files
  or implementation changes (P6 scoping).
- The commit is an automated checkpoint; it does not push. Push only if the user asks.
- `.active_feature` is gitignored (P7); the four feature artifacts are committed (P3).
