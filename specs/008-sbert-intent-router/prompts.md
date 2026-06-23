# Feature 008 — Prompts (Audit Trail, Constitution P3)

Chronological log of the LLM prompts that shaped this feature. Each entry is in
the spec-driven **Deliverable / Acceptance / Constraint / Outcome** format .

---

## P-1 — V1 architecture pivot to SBERT lightweight router (2026-06-23)

**Deliverable.** A new feature directory `specs/008-sbert-intent-router/` with
`spec.md` + `plan.md` + audit files, replacing the planner/orchestrator path
shipped in features 002/007 for the v1 demo.

**Acceptance.**
- Spec lists exactly six intents (`search_products`, `add_product`,
  `update_product`, `delete_product`, `get_my_listings`, `get_categories`) plus
  an `unknown` fallback.
- Spec names the model (`sentence-transformers/all-MiniLM-L6-v2`).
- Spec mandates **no LLM call** on the request path; entity extraction is
  regex + SBERT-for-category only.
- Spec includes a local **stub** of the feature-006 products API with the
  forward-compatible query params (`q`, `max_price`, `min_price`, `category`,
  `vendor_id`).
- Spec preserves feature 007's `/api/chat` request and response wire shape so
  the frontend chatbot UI is unmodified.
- `plan.md` is dry-run only — zero implementation files altered until the user
  approves.

**Constraint.**
- Outranked by `specs/constitution.md` (P1 — plan-first; P2 — no guessed
  decisions; P3 — full audit trail; P6 — idempotent edits; P7 —
  `.active_feature` binding).
- Read-only on the entire `local-marketplace2/` tree (the other engineer's
  branch). May reference for contract shapes only.
- Read-only on `backend/agent/` (feature 002 modules). Code stays in-tree but
  becomes unreachable on the wire after the chat-route rebinding in
  `backend/app/main.py`.

**Outcome.**
- Spec and plan authored 2026-06-23.
- Eight design forks raised explicitly to the user before drafting (Q1..Q8);
  all resolved: replace-on-the-wire, stub-locally, six intents,
  regex+SBERT-category, MiniLM-L6-v2, slot `008-sbert-intent-router`, richer
  stub query params, reuse `/api/chat` *plus* add `/api/agent/route`.
- Two `[NEEDS CLARIFICATION]` items deferred (spelled-out numerals,
  multilingual queries) — recorded in `spec.md` §6.

---

## P-2 — Implementation execution

**Deliverable.** Implementation of M1..M8 per `plan.md`, in order.

**Acceptance.**
- All §3 Success Criteria in `spec.md` met.
- `make router-test` green; `ruff check` clean.
- `npm run lint` and `npm run build` clean in `frontend/`.
- No file under `backend/agent/` or `local-marketplace2/` modified.

**Constraint.**
- Constitution P1 — this prompt does NOT execute until the user approves
  `plan.md`.
- Each milestone's "Verify" step in `plan.md` is its own gate; a failed verify
  rolls back the milestone before the next one begins.

**Outcome.** _Done (2026-06-23)._
- 85 backend unit tests pass (`make router-test` — products stub, SBERT
  loader, entities, router dispatch, three endpoint adapters).
- `ruff check` clean across feature-008 code.
- Frontend `npm run lint` and `npm run build` (104 modules) clean.
- One acceptance bar — `make sbert-test` end-to-end accuracy — deferred
  because the network blocks huggingface.co downloads (corporate
  proxy SSL). The loader-decision tests confirm the loader will use the
  pre-downloaded snapshot once `make sbert-download` runs on a network
  with `huggingface.co` access; the accuracy gate is wired and will
  trigger as soon as that happens. Logged in `conversation-history.md`
  Session 2.
- Five files outside `backend/app/{agent_router,products_stub}/` were
  touched (config keys, sqlite-tolerant session, model `__init__` guard,
  main.py wiring, frontend productContext reducer). Each is listed with
  its justification in `conversation-history.md` Session 2 under
  "Justified deviations".

---

## P-3 — V1 cleanup & real-006 cutover (2026-06-23)

**Deliverable.** Replace the in-memory `backend/app/products_stub/` with the
just-merged real Feature 006 service, remove every untracked V1 scaffold that
duplicates committed code, and keep the chat / search / agent wire shapes
identical.

**Acceptance.**
- `backend/app/products_stub/` deleted; `main.py` mounts the real
  `/api/products` and `/api/catalog` routers from Feature 006.
- `agent_router/route.py` dispatches via `_db_session()` (sync `SessionLocal`)
  into `services.product_service` instead of the stub store.
- Only **untracked** files/folders are removed (user override of the earlier
  blanket-delete plan). Anything committed to `main` stays.
- The three missing 006 ORM model files
  (`backend/app/models/{category,product,subcategory}.py`) are authored to
  fill the upstream gap, using 006's documented `String(36)`-vs-`UUID`
  convention.
- Spec §9 addendum records the cutover so the original FR-9 wording
  ("stub") is superseded without being rewritten (Constitution P6).
- `test_products_stub.py` removed; `test_agent_router.py` rewritten to use
  the existing `catalog_db` fixture (SQLite, seeded) and a `patched_session`
  fixture that redirects `route._db_session` to the test session.

**Constraint.**
- Constitution P6 — keep all committed feature-002 / addendum / spec
  content. Delete only what is untracked.
- Wire shapes the frontend consumes (`/api/chat`, `/api/agent/route`,
  `/api/search`) MUST be identical pre- and post-cutover.

**Outcome.** _Done (2026-06-23, conversation-history Session 3.)_
- 85 unit tests still green after the swap; `test_products_stub.py`
  removed in the same commit that introduced the cutover.
- One real upstream bug surfaced and logged but **not** fixed in this
  session (out of scope): `catalog/parser.py` rejects thousands-separator
  prices like `"₹45,000"` — owned by Feature 006.

---

## P-4 — Post-launch stabilisation wave (2026-06-23)

**Deliverable.** A working developer loop end-to-end (`make run` →
register → login → search → add → list) on a clean machine, plus the SBERT
classifier and parser fixes that came out of dogfooding the loop.

**Acceptance.**
- Six concrete bugs (numbered #1, #3, #4, #5, #6, #7 in spec §A.8) are
  closed:
  1. `make run` no longer raises `sqlite3.OperationalError: no such table:
     products / categories` on a clean checkout.
  3. SBERT no longer misclassifies terse imperatives:
     `"add iPhone 50000"` → `add_product` (not `update_product`);
     `"Add Amul milk for 29"` → `add_product` (not `delete_product`).
  4. `/api/orders` returns `200 []` for GET and `501` for POST (no more
     red "Failed to load orders" banner).
  5. The chatbot voice button auto-submits when the textarea is empty,
     and appends-only when the user is already typing.
  6. `catalog/parser.py` accepts bare numbers (`"… for 29"`) and
     thousands separators (`"₹45,000"`); SKU tokens like `"item-77"` are
     no longer mis-parsed as prices; chat-added products default to
     `stock_quantity = 1` (no longer ship "Out of stock").
  7. Customer registration no longer fails with `attempt to write a
     readonly database`: the local SQLite path is now absolute and
     anchored to the project root (`_PROJECT_ROOT`), independent of the
     process `cwd`.
- A debug badge surfaces SBERT `intent` + confidence on bot replies in
  the chatbot (user opt-in via the `debug` field in the response).
- Vendor-side search returns results in the UI as well as the chatbot
  (graceful read of both `{products}` and `{results}` response shapes).

**Constraint.**
- No edits to `backend/agent/` (Feature 002 code stays dormant per FR-14).
- The bare-number / comma-price parser rule lives in
  `backend/app/catalog/parser.py` (owned by 006 in spirit) and is tagged
  in the conversation history; if 006 amends its parser upstream we will
  reconcile.

**Outcome.** _Done (2026-06-23, conversation-history Sessions 4–8.)_
- Files touched: `backend/app/main.py`, `backend/app/models/*.py`,
  `backend/app/agent_router/intents.py`, `backend/app/api/routes/orders.py`,
  `backend/app/catalog/parser.py`, `backend/app/db/session.py`,
  plus the frontend `SearchPage.jsx`, `productContext.jsx`,
  `chatbotContext.jsx`, and `MessageBubble.{jsx,css}`. All listed
  individually in conversation history.
- Regression tests added: imperative-verb tiebreaker tests in
  `backend/tests/test_intent_classifier.py`, parser table-test for
  comma/bare-number prices.

---

## P-5 — Eliminate `/api/chat` double-fire + route Add-Product modal via SBERT (2026-06-23)

**Deliverable.** A single user action (chatbot voice-add **or** Add-Product
modal voice-add) produces exactly one `/api/chat` POST and exactly one DB
row, and the modal's "Create from description" button (text or voice) goes
through the SBERT chat path with `intent="add_product"` so it cannot be
silently mis-classified.

**Acceptance.**
- Server log shows exactly **one** `POST /api/chat` per send, in dev
  (React 18 StrictMode) and prod. No paired POSTs on different ports.
- `chat_adapter` accepts an optional `intent` field on JSON and
  multipart bodies, validates it against an allow-list
  (`_ALLOWED_FORCED_INTENTS`), and forwards it as `forced_intent` to
  `route_text`. Unknown values are silently dropped (no 400).
- `VendorPage.createFromDescription` calls
  `sendChat(text, null, null, "add_product")` and the row is created
  via `route_text` → `product_service.create_from_description`. Errors
  (parser refusal, etc.) surface in the modal's error banner.
- The modal's voice button auto-submits when the description textarea
  is empty; appends otherwise — same UX contract as the chatbot.
- Three new tests in `backend/tests/test_chat_router.py` cover the new
  `intent` field: forwarded-when-valid, silently-dropped-when-unknown,
  forwarded-via-multipart.

**Constraint.**
- The side-effect must move **outside** the `setText(prev => …)` updater
  to survive StrictMode double-invocation (root cause of the duplicate
  POSTs).
- Single-shot guards (`submittingRef`, `runningRef`, `creatingRef`) use
  `useRef` and are cleared on the next macrotask — not on render.
- The chat wire shape `{message, sessionId, intent?}` →
  `{reply, listings, sessionId}` stays backward compatible: the
  `intent` field is optional and old clients keep working.

**Outcome.** _Done (2026-06-23, conversation-history Sessions 9–10.)_
- Backend: `backend/app/agent_router/chat_adapter.py`,
  `backend/app/agent_router/route.py`, `backend/tests/test_chat_router.py`.
- Frontend: `frontend/src/components/chatbot/ChatInput.jsx`,
  `frontend/src/components/products/ProductExtractPanel.jsx`,
  `frontend/src/pages/VendorPage.jsx`,
  `frontend/src/services/chatbotService.js`,
  `frontend/src/services/apiError.js`.
- Verified manually: one voice-add ⇒ one POST ⇒ one row, both surfaces.

---

## Recurring interactions (Constitution P3 — ranked frequency)

Updated at session close. Threshold for `[SKILL CANDIDATE]` is 3 recurrences.
Ordered most-frequent first.

| Count | Interaction | Promotion candidate? |
| :--: | :-- | :-- |
| 4 | "Mirror the audit-file style of the previous feature (`spec.md` / `plan.md` / `prompts.md` / `conversation-history.md`)" (features 002, 005, 007, 008) | **[SKILL CANDIDATE]** — scaffold the four audit files from a one-line feature description. |
| 3 | "Voice input should auto-submit when the field is empty, append otherwise" (chatbot ChatInput — session 6; chatbot StrictMode rework — session 9; Add-Product modal ProductExtractPanel — session 10) | **[SKILL CANDIDATE]** — a reusable `useVoiceAutoSubmit(ref, onSubmit)` React hook + matching `useSingleShotGuard()` for StrictMode-safe single-action handlers. |
| 3 | "Bypass SBERT classification with a forced intent for a specific UI flow" (Add-Product modal `intent="add_product"` — sessions 9 & 10; the search adapter already forces `search_products` server-side from inception) | **[SKILL CANDIDATE]** — formalise `forced_intent` as a first-class field in the agent-router contract docs; add a `forceIntent(text, intent)` helper to `chatbotService.js`. |
| 3 | "Stub another engineer's not-yet-merged API and tag with `# STUB-<feat>`" (features 007 partial, 008 explicit, prior ad hoc) | **[SKILL CANDIDATE]** — a "scaffold-006-style-API-stub" skill would save 30 min per cross-team integration. |
| 3 | "Review and humanise an existing spec/doc — clean, clear, spec-driven, append-only" (this prompt repeated three times in session 11 alone, plus the spec-cleanup arc in session 3) | **[SKILL CANDIDATE]** — a `humanise-spec` skill that prepends a "Reader Start Here" section while honouring Constitution P6's append-only rule. |
| 2 | "Replace the heavy planner/orchestrator path with a lightweight router for v1" (features 007 partial; 008 full) | Not yet (≥3 needed). |
| 2 | "An upstream/cross-team bug surfaced through my code — fix it here or leave it for the owning feature?" (006 catalog parser bare-numbers/commas — session 8 fixed; thousands-separator already on 006's plate — session 3 deferred) | Not yet (≥3 needed). |
| 2 | "A previous fix only addressed the symptom — the side-effect is *inside* a React updater, refactor it out and add a single-shot guard" (chat input — session 9; Add-Product modal — session 10) | Not yet (≥3 needed); will reach 3 the next time React StrictMode bites and graduate the hook above. |
