# Prompts — Feature 002: Frontend

Chronological log of the LLM prompts/interactions for this feature (Constitution P3).
Secrets are never recorded here (P4).

## Chronological log

### 2026-06-18

1. **User (kickoff):** Develop the frontend feature using the existing scaffold and the
   `002-frontend-SPEC.md` spec. Create a frontend-related `CLAUDE.md` and `PLAN.md` in
   `specs/002-frontend/`, create required root-level folders, execute the plan step by
   step with user acceptance, do not assume anything (ask on doubt), and follow
   `constitution.md`.
2. **Agent → User (clarifying questions):** Surfaced fail-closed `.active_feature`
   (missing), missing audit artifacts, and four substantive ambiguities:
   (a) React 18 vs 19+; (b) Context API vs Redux `store/` layout; (c) backend has only
   `/health` — how to integrate; (d) `CLAUDE.md`/`plan.md` placement.
3. **User (answers):** D1 React 19+ · D2 Context API · D3 mock against assumed contract ·
   D4 both files in `specs/002-frontend/`.
4. **Agent:** Set `.active_feature=002-frontend`; wrote `plan.md` (dry-run) with 9 phases;
   awaited approval (P1).
5. **User:** "approve, start Phase 0".
6. **Agent:** Phase 0 — created `spec.md`, `CLAUDE.md`, `prompts.md`,
   `conversation-history.md`; appended Feature-002 entry to `docs/architecture.md`.

## Recurring interactions

_(Tracked by intent; flagged `[SKILL CANDIDATE]` at ≥3 occurrences — default threshold.)_

| Intent | Count | Flag |
| :-- | :-: | :-- |
| "Don't assume — ask on ambiguity before acting" | 1 | — |
| "Phase complete → stop for user acceptance" | 1 (recurs per phase) | watch |
| "Honor constitution slice/idempotency rules" | 1 | — |

_No interaction has reached the ≥3 threshold yet._
