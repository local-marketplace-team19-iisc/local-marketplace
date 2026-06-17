# Prompts — Feature 000: App Scaffold

Chronological log of LLM prompts for this feature (Constitution P3).

## Chronological log

1. **"validate SPEC.md and ensure there is no silent assumption and spec is deterministic"**
   — Full validation pass; reported silent assumptions / non-determinism findings.
2. **"treat the scaffold as 'feature 000,' governed but not a product feature and update the spec"**
   — Reframed scaffold as feature 000 across SPEC §4/§5/§7/§8.
3. **"No specific spec.md to be generated for 000-app-scaffold and master spec is the app scaffold spec."**
   — Recorded the feature-000 `spec.md` exemption (master SPEC.md is its spec).
4. **"Evaluate SPEC.md to see if there are any more unknowns"**
   — Second evaluation pass; flagged regressions + remaining unknowns.
5. **"constitution.md exists now under specs/"**
   — Cross-checked constitution vs SPEC.md; found P3 conflict (since resolved).
6. **"SPEC.md and constitution.md updated. Evaluate now."**
   — Third evaluation pass; flagged new contradictions (privacy, fulfillment, admin).
7. **"Execute SPEC.md" → "Approve."**
   — Wrote `plan.md` (dry-run), got approval (P1/§8), scaffolded the FastAPI app.
8. **"Before that... ensure every feature has version-controlled spec.md/conversation-history.md/prompts.md. Update constitution Principle 3. Also make sure conversation history logs all sessions and decisions..."**
   — Rewrote Principle 3 (version control + append-only session log); kept 000 exemption.
9. **"update the constitution.md principle 3 for version-controlled prompts.md which logs recurring interactions by ranking prompts by frequency, flagging... candidates to be converted into skills."**
   — Added the recurring-interactions ranking + `[SKILL CANDIDATE]` rule (≥3 threshold).
10. **"Run the app again" (on port 8081)**
    — Ran the scaffold on :8081; verified `/health` → `200 {"status":"OK"}`, `/docs` → `404`.
11. **"000-app-scaffold does not has the all conversation-history.md and prompts.md"**
    — Brought this log and `conversation-history.md` fully up to date.

## Recurring interactions

Repeated prompts (verbatim or by intent), ranked by frequency. Any interaction
recurring **≥3 times** is flagged `[SKILL CANDIDATE]` for promotion into a reusable
skill (Constitution P3).

| Count | Interaction (by intent) | Source prompts | Flag |
| :-- | :-- | :-- | :-- |
| 3 | Validate / evaluate a spec for silent assumptions, unknowns & determinism | #1, #4, #6 | `[SKILL CANDIDATE]` |
| 2 | Update / reframe SPEC.md | #2, #3 | — |
| 2 | Update constitution Principle 3 (audit-trail rules) | #8, #9 | — |
| 1 | Execute spec → approved-plan-then-implement | #7 | — |
| 1 | Run the app & verify `/health` | #10 | — |
| 1 | Reconcile / complete audit artifacts | #11 | — |

**Action:** "Validate/evaluate a spec for silent assumptions & determinism" has
recurred 3× → strong candidate for a `spec-validate` skill (deterministic checklist:
undefined terms, unquantified thresholds, cross-doc contradictions, missing-section
numbering, [NEEDS CLARIFICATION] coverage).
