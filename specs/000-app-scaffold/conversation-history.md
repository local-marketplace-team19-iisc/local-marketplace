# Conversation History — Feature 000: App Scaffold

Append-only, cumulative audit log (Constitution P3). Each session is added below;
earlier entries are never edited or removed. Newest entries go at the bottom.

---

## Session 1 — Spec validation & scaffold execution (2026-06-17 → 2026-06-18)

### Context / goal
Validate `SPEC.md` (and later `constitution.md`) for silent assumptions and
non-determinism; reframe the app scaffold as feature 000; then execute the scaffold.

### Decisions made (+ reasoning)
- **Scaffold = feature 000, governed but not a product feature.** It delivers the
  runnable starting point, not a user journey, so it is tracked/governed but kept
  distinct from product features 001+.
- **Feature 000 has no own `spec.md`** — the master `SPEC.md` is its spec, to avoid
  duplicating the contract. Wired as an explicit exemption in Constitution P3.
- **Disable FastAPI auto-docs** (`docs_url/redoc_url/openapi_url=None`) to satisfy
  SPEC §7 "no route other than `/health`". The `later` "generated openapi.json" can
  still be produced programmatically via `app.openapi()`.
- **PORT rebind via `pydantic-settings`** — run command `python -m backend.app.main`
  reads `PORT` from env → `uvicorn.run(port=settings.PORT)`.
- **`CLAUDE.md` left untouched** — Constitution P5 forbids AI from modifying it.
- **Dry-Run honored** — `plan.md` written and user-approved before any code (P1/§8).

### Edge cases / unknowns discovered
- **Privacy contradiction (open):** §6 says location "must not be persisted" yet also
  "saved/default address" is used — live geolocation vs. stored address are conflated.
  → product-feature `[NEEDS CLARIFICATION]`, not blocking 000.
- **Fulfillment model (open):** "location to be delivered" implies delivery, but no
  delivery journey exists. → `[NEEDS CLARIFICATION]`.
- **"admin" actor (open):** categories "created by admin" but no admin surface/auth.
- **Auth sequencing (open):** journeys require registered customer / onboarded vendor,
  but Auth is a `later` feature → product features 001+ depend on it.
- **Stock decrement atomicity (open):** concurrent last-unit orders unspecified.
- **Port 8000 collision (environmental):** an unrelated long-running `uvicorn
  app.main:app` already holds :8000 locally; verification was done on :8123. Not a
  defect in the scaffold; noted so a future session doesn't mistake it for one.

### `[NEEDS CLARIFICATION]` carried forward (product features, not 000)
Privacy split (geolocation vs saved address), fulfillment model, admin actor,
auth/onboarding sequencing, stock-decrement concurrency, payment (absent entirely),
openapi.json generation step.

### Outcome
Scaffold implemented and verified: `/health` → `200 {"status":"OK"}`; `/docs`,
`/redoc`, `/openapi.json` → `404`; `PORT` rebinds; `pytest` (2 passed) and
`ruff check .` clean. All SPEC §7 criteria met (Docker check optional, not run).

---

## Session 2 — Strengthen audit governance (2026-06-18)

### Context / goal
Ensure every feature has version-controlled `spec.md` / `prompts.md` /
`conversation-history.md`, and that the history logs all sessions, decisions,
edge-case discoveries, and reasoning so nothing is lost across sessions.

### Decisions made (+ reasoning)
- **Constitution P3 rewritten** to require all three artifacts be committed to Git
  (never gitignored/local-only), to keep the feature-000 `spec.md` exemption (user
  confirmed), and to define `conversation-history.md` as an append-only, per-session
  log capturing context, decisions+reasoning, edge cases, and `[NEEDS CLARIFICATION]`.
- **SPEC.md §8 aligned** with the new P3 wording.
- **This file reformatted** into per-session entries to comply going forward.

---

## Session 3 — prompts.md recurrence → skill candidates (2026-06-18)

### Context / goal
Make `prompts.md` not just a log but a ranked backlog: detect recurring prompts and
flag those worth turning into skills.

### Decisions made (+ reasoning)
- **Constitution P3 extended:** `prompts.md` must include a "Recurring interactions"
  section listing repeated prompts with occurrence counts, ranked most-frequent-first,
  flagging any recurring interaction as `[SKILL CANDIDATE]`.
- **Concrete threshold = ≥3 occurrences (default).** Chose a number rather than an
  undefined "threshold" because an unquantified rule in a governing doc violates P2
  (unambiguous specs).
- **SPEC.md §8 + feature-000 `prompts.md` aligned** to the new format.

### Edge cases / unknowns discovered
- **No tooling auto-counts frequency** — the rule is currently discipline-enforced by
  the model, not automated. Flagged a hook/skill as a future option (not built).

---

## Session 4 — Run the app on :8081 (2026-06-18)

### Context / goal
Run the scaffold again; user requested port 8081.

### Decisions made (+ reasoning)
- Ran with `PORT=8081 python -m backend.app.main` (explicit env override).

### Edge cases / unknowns discovered
- **`.env.example` is not read at runtime** — `pydantic-settings` reads `.env`. The
  edited `.env.example` (PORT=8081) does not change the app default (still 8000 in
  `config.py`); a real `.env` would. Verified `/health` → `200 {"status":"OK"}`,
  `/docs` → `404` on :8081.

---

## Session 5 — Complete the audit artifacts (2026-06-18)

### Context / goal
User noted `conversation-history.md` and `prompts.md` did not capture all sessions/
prompts. Brought both fully up to date per Principle 3.

### Decisions made (+ reasoning)
- **`prompts.md` rewritten** with the full 11-prompt chronological log + recurrence
  table. "Validate/evaluate a spec for determinism" reached 3× → flagged
  `[SKILL CANDIDATE]` (a `spec-validate` skill).
- **This file** appended with Sessions 3–5 so no prior session is lost.
