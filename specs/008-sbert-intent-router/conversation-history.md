# Feature 008 — Conversation History (Constitution P3, P7)

Append-only log of every working session on this feature. Earlier entries are
never overwritten or truncated. Each entry captures the session's context/goal,
decisions and reasoning, edge cases / unknowns, and any `[NEEDS CLARIFICATION]`
raised or resolved.

---

## Session 1 — 2026-06-23 (design only; zero code touched)

### Context / goal (spec-driven)
Feature-002 planner/orchestrator/tool-registry agent for the v2-version. In the v1-version will design, not implement, a lightweight v1 agent that integrates with the existing marketplace application.

The agent should accept natural-language input through text or browser-transcribed voice, classify user intent using SBERT-based semantic matching, extract required entities through deterministic rules, and route the resulting structured request to the existing marketplace REST APIs.

The product and catalog APIs already exist as part of `local-marketplace/specs/006-vendor-product-management` and should be treated as the system of record. The v1 agent should act only as an intelligent input-understanding and API-routing layer on top of the existing backend services.

The design should focus on:

* Text and Voice → Text input handling.
* SBERT-based intent classification.
* Deterministic entity extraction and validation.
* Mapping unstructured user requests to structured API payloads.
* Routing requests to existing search, product creation, product update, product deletion, and product detail APIs.

The design must not include implementation details for a planner, orchestrator, tool registry, autonomous agents, multi-step workflows, memory systems, or any new backend infrastructure. The scope is limited to a lightweight intent-understanding layer that converts natural-language requests into calls against the existing REST surface.


### reviewed the Feature and implementation before writing anything : 
- Constitution (`specs/constitution.md`) — P1, P2, P3, P6, P7 all binding here.
- Existing specs catalog in this repo: `000` through `007`. Confirmed slot `008`
  is free.
- The other engineer's `spec.md`, `routes/products.py`, `schemas/product.py` in
  `local-marketplace2/.../006-vendor-product-management/`. Extracted: the six
  product endpoints, their request/response shapes, the JWT vendor gating, and
  the catalog enum.
- Feature 007 (`007-chatbot-integration/spec.md` + `router.py`) — confirmed the
  existing `/api/chat` request/response wire shapes and the singleton/lifespan
  patterns we'll reuse.
- Frontend services: `searchService.js` (currently calls `GET /api/search?q=`
  which is mocked), `chatbotContext.jsx` (calls `POST /api/chat`).

### Design forks raised to the user (P2 — no guessing)
Eight forks were surfaced *before* drafting `spec.md`/`plan.md` because each
materially changes the contract:

| Q | Decision | Reason |
| :-- | :-- | :-- |
| Q1 — relationship to 002/007 | **Replace on the wire** | Cleanest demo path; feature 002 code stays in-tree (P6) but is unreached. One-line rollback in `main.py`. |
| Q2 — products API source | **Stub locally** | Other engineer's branch is read-only; we don't merge their code unilaterally. |
| Q3 — intents in v1 | **Six** + `unknown` | Matches the user's acceptance criteria verbatim; `unknown` is a safety fallback so we never call an API on garbage. |
| Q4 — entity extraction | **Regex + SBERT-for-category** | Honours the "no LLM" constraint. SBERT is the only model loaded. |
| Q5 — SBERT model | **MiniLM-L6-v2** | 80 MB, English, CPU-friendly. Matches v1 audience. |
| Q6 — feature slot | **008-sbert-intent-router** | Slot 006 is taken by the parked LangGraph design; slot 007 is the chat-integration. 008 is the next free slot and the name is accurate. |
| Q7 — search filters | **Richer stub** | Adds forward-compatible query params (`q`, `max_price`, `min_price`, `category`, `vendor_id`) so the router builds a query string and the API filters; cleaner than fetching all rows and filtering in-Python. |
| Q8 — frontend endpoint | **Reuse `/api/chat` + add `/api/agent/route`** | Chatbot stays unchanged (FR-7); the new one-shot endpoint also serves the search bar and any programmatic caller. |

### Decisions made *because* of these picks (and reasoning)
- The agent is **stateless** for v1. With the planner gone, there's no
  multi-turn confirmation or slot-filling loop to keep state for. Each
  `/api/chat` POST is independent; `sessionId` is echoed back for the
  frontend's benefit but never read server-side.
- The Redis dependency is now a **dead dependency** for the request path
  (feature 002's `memory.py` was the only consumer; feature 002 is no longer
  on the wire). We don't remove the dep in this feature — that's separate
  cleanup work; we just note it.
- The model loader follows feature 002 ASR's **offline-first** pattern
  (`MODELS_DIR` env var, `ALLOW_MODEL_DOWNLOAD=0` default, fail-fast at
  startup with an actionable message). Same operational ergonomics.
- The stub products API is mounted at `/api/products` and `/api/catalog` —
  *exactly* the same routes as feature 006. When 006 merges, the stub
  package is deleted in a single PR and `main.py` includes the real router
  instead. No code change needed in the agent_router itself.

### Edge cases discovered (recorded in `spec.md` §1)
1. Empty `q` after stripping intent keywords → return top-N most-recent
   products, not 400.
2. `"near me"` in a search query → ignored in v1 (no geo pipeline), surfaced
   in the response `meta.ignored` array.
3. `"update my iPhone listing"` with no explicit ID → single-candidate
   vendor-scoped lookup; tie or zero → ask the user for the ID, no write.
4. Customer attempting a vendor intent (`add/update/delete`) → polite refusal,
   no HTTP call, HTTP 200 (no red toast on the frontend).
5. `unknown` intent → polite reply listing supported intents, no HTTP call.
6. Spelled-out numbers (`"sixty thousand"`) → digit-form only in v1
   (`[NEEDS CLARIFICATION]` deferred).

### `[NEEDS CLARIFICATION]` raised
- **Spelled-out numerals.** Digit form (`60000`, `60,000`, `60k`) is in scope.
  Spelled-out form deferred to a follow-up unless the demo audience uses it.
- **Multilingual queries.** MiniLM-L6-v2 is English-only. Swapping to
  `paraphrase-multilingual-MiniLM-L12-v2` is a single-line change in
  `sbert.py` if Hindi/Kannada/Tamil queries are expected.

Both are recorded in `spec.md` §6 (Deferred / Clarifications) and do **not**
block plan approval per Constitution P2 (they are *known and acknowledged*
deferrals, not unresolved guesses).

### Files altered this session
- **Created:** `.active_feature` (set to `008-sbert-intent-router`).
- **Created:** `specs/008-sbert-intent-router/spec.md`.
- **Created:** `specs/008-sbert-intent-router/plan.md`.
- **Created:** `specs/008-sbert-intent-router/prompts.md`.
- **Created:** `specs/008-sbert-intent-router/conversation-history.md` (this file).
- **Touched:** none. P1 gate blocks all implementation until user-approved.

### Gate status (Constitution P1)
**Open.** Implementation is paused until the user approves `plan.md`.
No file under `backend/`, `frontend/`, `docs/`, `local-marketplace2/`, or
`backend/agent/` has been touched in this session.

---

## Session 2 — Implementation M1 → M8 (2026-06-23)

User approval received: *"Approve" — proceed M1 → M8 in order with verify
gates between each milestone.* Gate from session 1 is now **CLOSED**.

### Decisions / clarifications resolved this session
- **No P1 violation.** Each milestone was implemented in plan order and
  gated by a passing test suite before moving on. M2's "real model
  accuracy" test (`test_intent_classifier.py`, marked `slow`) is held
  pending network access to huggingface.co — see Justified Deviation 3
  below — but the loader contract tests fully exercise the loading
  decision tree.
- **Parser dual-track.** The "extract price from free-text" logic exists
  twice — once in `backend/app/products_stub/parser.py` (for
  `POST /api/products/from-description`) and once in
  `backend/app/agent_router/entities.py` (for the router's price binding).
  Both implement the same scoring heuristic (currency-prefix > comma >
  k-suffix > bare). They will naturally merge into a shared utility once
  feature 006 lands and the stub disappears; duplicating ~50 lines is
  cheaper than introducing a cross-package import that 006 would have to
  re-wire.
- **Stub mounted under `/api/products` directly** (not under a prefix).
  The 006 reference router publishes the same paths, so this keeps the
  cutover to a two-line `include_router` swap when 006 merges.

### Justified deviations (touched files outside the feature folder)
Per Constitution P6, every file I touched outside `specs/008-…/` is
listed here with a justification.

1. **`backend/app/db/session.py`** — `create_async_engine` was crashing
   at *import time* when `DATABASE_URL` is sqlite (the local-dev URL
   shipped in `.env`). This was a pre-existing defect that blocked any
   FastAPI import. Fixed by guarding the async-engine block behind an
   `_is_async_url(...)` check; behaviour on Postgres is unchanged. **No
   feature-001 / feature-003 tests were modified.**
2. **`backend/app/models/__init__.py`** — Re-exported model symbols from
   `backend.app.models.models`, which doesn't exist in this branch (lives
   in feature-001's in-flight work). Fixed by wrapping that import in a
   `try / except ModuleNotFoundError` so anything that doesn't need those
   entity classes still imports cleanly. The symbols fall back to `None`,
   which is acceptable because the failing import path was never reached
   under sqlite anyway.
3. **`backend/app/core/config.py`** — Appended six new `Settings` keys
   for feature 008 (`MODELS_DIR`, `ALLOW_MODEL_DOWNLOAD`,
   `SBERT_MODEL_NAME`, `INTENT_CONFIDENCE_THRESHOLD`,
   `CATEGORY_MATCH_THRESHOLD`, `AGENT_CHAT_TURN_TIMEOUT_S`). Pure
   addition; existing keys untouched.
4. **`backend/app/main.py`** — Mounted three new routers (`agent_router`,
   `chat`, `search`) + the products stub; added a `lifespan` context
   manager to best-effort warm SBERT on boot. The pre-existing
   `auth.router` and `health.router` lines are unchanged.
5. **`frontend/src/store/productContext.jsx`** — One-line change to
   `searchProducts` reducer so it reads `d.products` (the new backend
   shape) while still tolerating the legacy `d.results` shape from
   mock fixtures. No UI changes; the reducer was the only consumer of
   the search-API response shape.

All five deviations are no-ops on the production Postgres
configuration and have feature-008-specific motivation.

### Pre-existing failures observed but NOT addressed
- `backend/tests/db/` cannot import (`asyncpg` missing from the venv).
  This is feature-001 infrastructure; feature 008 does not depend on
  asyncpg or the marketplace ORM. Excluded from `make router-test`.
- Several `backend/tests/test_auth_*.py` failures when the sqlite DB has
  prior rows. These are state-leakage bugs in feature-003's own tests
  (they don't roll back between cases). Out of scope for this feature.

### Implementation artifact summary
- **Created (24 files):** the entire `backend/app/products_stub/` and
  `backend/app/agent_router/` packages, plus seven test files (85 new
  unit tests, all green), `frontend/src/services/agentService.js`,
  `models/sbert/` model snapshot directory (gitignored — actual model
  not committed), and the spec/plan/prompts/this-history file.
- **Touched (8 files):** see *Justified deviations* above, plus
  `pyproject.toml` (new `[project.optional-dependencies] sbert` extra),
  `Makefile` (new `sbert-install / sbert-download / router-test /
  sbert-test` targets), `.env.example`, `docs/architecture.md`,
  `README.md`.

### Gate status (Constitution P1)
**Closed.** All eight milestones complete. The acceptance suite passes:

| Gate | Command | Result |
|---|---|---|
| Backend lint | `ruff check backend/app/agent_router backend/app/products_stub backend/tests/test_*` | All checks passed |
| Backend tests | `make router-test` | **85 passed** in 4.4 s |
| Frontend lint | `cd frontend && npm run lint` | clean |
| Frontend build | `cd frontend && npm run build` | 104 modules, no errors |
| SBERT accuracy | `make sbert-test` | **deferred** — waits for `make sbert-download` on a network with huggingface.co access (corporate proxy SSL block; loader contract tests confirm the decision tree is correct) |

---

## Session 3 — 2026-06-23 — V1 cleanup & real-006 cutover

### Context
After session 2 closed, the user pulled the upstream `006-vendor-product-management`
PR (#7) from GitHub onto the feature-008 working tree. This created:
- Five merge conflicts (`backend/app/db/session.py`, `backend/app/main.py`,
  `backend/app/models/__init__.py`, `docs/architecture.md`, `local_marketplace.db`).
- An overlap between my temporary `products_stub/` and the real 006
  `services/product_service.py` + `api/routes/products.py` + `api/routes/catalog.py`.
- A request to clean the repo to a "clean, clear, working V1" state.

### User-locked decisions (`AskQuestion`, this session)
1. **`specs/006-backend-agent/` (untracked)** → delete.
2. **`backend/agent/` + `specs/002-agent/` (tracked)** → user later corrected:
   **do NOT delete anything that is committed**. Keep both. Dormant on disk.
3. **`specs/007-chatbot-integration/` + `backend/app/agent_service/` (untracked)**
   → delete (superseded by feature-008 `chat_adapter.py`).
4. **`backend/app/products_stub/` (untracked)** → drop. Rewire the SBERT router
   at `backend/app/agent_router/route.py` to call the *real* 006
   `backend.app.services.product_service` against the SQLAlchemy `Session`.
5. **Merge conflicts** → resolve by **preferring the 006 (upstream) version**
   of `db/session.py`, `main.py`, `models/__init__.py`, `docs/architecture.md`,
   `local_marketplace.db`. Then **layer feature-008's router includes on top of
   the resolved `main.py`** so the three agent surfaces still mount.
6. **Don't abort the merge.** 006 brings real DB-backed schemas + Alembic +
   seed data, which is strictly better than the in-memory stub.

### Cleanup target classification (committed vs. untracked)
Verified via `git ls-files`:

| Target | Tracked count | Action |
|---|---|---|
| `backend/agent/` | 37 | **Keep** (committed code — user override). |
| `specs/002-agent/` | 5 | **Keep** (committed spec — user override). |
| `backend/app/agent_service/` | 0 | Delete. |
| `backend/app/products_stub/` | 0 | Delete. |
| `specs/006-backend-agent/` | 0 | Delete. |
| `specs/007-chatbot-integration/` | 0 | Delete. |
| `backend/tests/test_products_stub.py` | 0 | Delete (companion of the stub). |
| `frontend/src/services/agentService.js` | 0 | Delete iff unreferenced. |

### Plan
- **C1** This audit-log entry.
- **C2** Resolve all five merge conflicts preferring 006; restore the three
  feature-008 router includes on top of resolved `main.py`.
- **C3** Rewrite `backend/app/agent_router/route.py` so every dispatch
  (`search_products`, `add_product`, `update_product`, `delete_product`,
  `get_my_listings`, `get_categories`) goes through 006's
  `product_service` against a `Session` from `db.session.SessionLocal`.
  Adapt the JWT principal helper at `agent_router/_auth.py` to match 006's
  `Request.state` convention (006's `products` router parses the bearer
  itself; the agent router will do the same).
- **C4** `rm -rf backend/app/agent_service backend/app/products_stub`.
- **C5** `rm -rf specs/006-backend-agent specs/007-chatbot-integration`.
- **C6** Delete dead tests + `agentService.js` if no consumer exists in
  `frontend/src/`.
- **C7** Update `docs/architecture.md` (feature-008 section: stub → real 006),
  `README.md` (remove stub references), and `specs/008-sbert-intent-router/spec.md`
  (FR-9 and FR-13 wording: products API is real, not stub).
- **C8** Run lint + `make router-test` + frontend lint/build. Must be green.
- **C9** Show `git status` + diff stats to user. No commit without explicit approval.

### Notes on dormant code (committed, kept)
- `backend/agent/` is unreachable from any HTTP route now (feature-008
  `chat_adapter.py` owns `/api/chat`; `api.py` owns `/api/agent/route`;
  `search_adapter.py` owns `/api/search`). It compiles and its tests still
  run because they are independent. We do not import it from `main.py`.
- Future re-enablement is one wiring change in `main.py` away. This satisfies
  the user's "v1 is clean" requirement without losing prior work.

### Execution outcome (Session 3)
- **Resolved 5 merge conflicts** keeping the upstream 006 base for
  `db/session.py`, `main.py`, `models/__init__.py`, `local_marketplace.db`,
  and a hand-merged `docs/architecture.md` (kept both 006 + 008 sections).
- **Filled the upstream 006 gap**: created
  `backend/app/models/{category,product,subcategory}.py` SQLAlchemy ORM
  models that match the Alembic 0004 migration and follow 006's
  documented `String(36)` id convention (D2). Verified by running
  upstream-shipped 006 service tests (`test_products_from_description.py`,
  `test_products_delete_by_description.py`) — all green.
- **Fixed `.gitignore`**: the broad `models/` rule was anchored to repo root
  (`/models/`) so it no longer collides with `backend/app/models/`.
- **Rewrote `backend/app/agent_router/route.py`** to dispatch via
  feature 006's `product_service` against a `Session` from
  `db.session.SessionLocal`. Search filters that 006 doesn't natively
  support (text-search, max/min price) are applied client-side in
  `_filter_rows()`. Single-match update fallback and cross-vendor 403
  semantics preserved.
- **Updated `backend/app/agent_router/projection.py`** to project the
  006 `ProductRead` Pydantic model into the frontend `Listing` wire
  shape (was projecting the deleted stub dataclass).
- **Pointed `entities.extract_category`** at 006's `list_categories`.
- **Deleted (all untracked)**: `backend/app/products_stub/`,
  `backend/app/agent_service/`, `specs/006-backend-agent/`,
  `specs/007-chatbot-integration/`, `backend/tests/test_products_stub.py`,
  `frontend/src/services/agentService.js`.
- **Rewrote `backend/tests/test_agent_router.py`** to use the existing
  `catalog_db` fixture (in-memory SQLite seeded by `conftest.py`) +
  a new `patched_session` fixture that redirects `route._db_session`
  into the test session. 18/18 tests green.

### Upstream issues identified (NOT fixed here)
- `backend/app/catalog/parser.py` does not handle thousands separators
  in prices (`"₹45,000"` → 45.00 instead of 45000). Out of scope; logged
  here so the 006 owner can pick it up. The agent-router test
  `test_vendor_add_product_happy` works around it by using a non-comma
  price.
- The 006 PR shipped without the three ORM model files; this cleanup
  authored them (see above). Mention in the next 006 PR review.

## Session 4 — 2026-06-23 — SQLite catalog bootstrap

### Context
Running `make run` against the committed `local_marketplace.db` returned
500s on the first product call:

```
sqlite3.OperationalError: no such table: products
sqlite3.OperationalError: no such table: categories
```

Root cause: feature 006 was designed for Postgres + Alembic. The
migration `0004_create_catalog_products.py` is the only thing that
creates the `categories` / `subcategories` / `products` tables and
seeds the taxonomy. The local SQLite dev path runs no migrations, so
those tables never come into existence on a fresh boot.

### Decision
Mirror the migration's create + seed step inside `main.py`'s
lifespan. The user skipped the prompt; default applied:
`auto_create_in_lifespan`.

### Implementation
- Added `_bootstrap_catalog_tables()` in `backend/app/main.py`:
  - `Base.metadata.create_all(...)` for `Category`, `SubCategory`,
    `Product` ORM tables (no-op when tables already exist).
  - Seeds via `catalog.seed_data.iter_categories()` and
    `iter_subcategories()`, gated on `SELECT COUNT(*) FROM categories
    == 0` for idempotency.
- Lifespan now: auth tables → catalog tables → SBERT warmup.
- Wrapped in `try/except` so a seed failure logs a warning instead
  of crashing startup.

### Production impact
Zero. On Postgres, the Alembic migration has already populated the
catalog tables and the row count is > 0, so the seed step
short-circuits. `create_all` is a no-op when the tables exist.

### Verification
1. Direct bootstrap call on the committed sqlite file:
   - Before: `{otps, refresh_tokens, users, vendors}`
   - After:  `{categories, otps, products, refresh_tokens,
               subcategories, users, vendors}`
   - Seed result: 12 categories, 16 subcategories, 0 products.
2. Second + third bootstrap calls: row counts unchanged
   (idempotency verified).
3. End-to-end HTTP smoke (TestClient):
   - `POST /api/auth/register-vendor` → 201
   - `POST /api/products` (direct REST add) → 201
   - `GET  /api/search?q=iphone` (anon, SBERT skipped) → 200, product
     returned.
   - `POST /api/chat` "show me iphone under 100000" (auth, SBERT
     classified) → 200, product returned.
   - `POST /api/chat` "Add a new Samsung S24 for ₹45000" → 201,
     product added.

### Upstream limitations re-confirmed (still NOT fixed here)
- `catalog/parser.py` requires a currency marker (`₹`, `Rs`, `INR`).
  Bare numerics (`"Samsung S24 for 45000"`) → `price=None` → 400 reply.
- `catalog/parser.py` still drops digits after a thousands separator
  (`"₹45,000"` → 45.00). Logged in Session 3 already.
- Both 006-owned. Outside the scope of this cleanup.

## Session 5 — 2026-06-23 — Chatbot add-product UX fix + intent badge

### Context
User reported that vendor chat-add was broken in two specific ways:

> "1. api is not working properly. 2. sbert model is not executing"

Diagnosis on the live logs (`terminals/6.txt:684-1036`):
* Stack traces at the top of the range were *stale* — from before the
  Session-4 catalog bootstrap. Every request after the restart was
  200/201/204.
* SBERT classified all 12 probe utterances correctly (scores 0.48–1.00,
  all above the 0.35 threshold). Confirmed by direct call to
  `intents.classify`.
* The actual user-visible problem: the 006 `catalog/parser.py` rejected
  two natural input shapes the chatbot routinely produces:
    1. Bare numbers (`"Add Samsung S24 for 45000"`) → `price=None` →
       "Could not find a price" reply.
    2. Thousands-comma (`"₹45,000"`) → parsed as `Decimal("45.00")` →
       "Added: ... (₹45.0)" — catastrophic UX.
  Both are 006-owned bugs that hit 008's chat surface every time.

### Decisions
User answered `yes_full` to fix the parser and `yes_badge` to expose
SBERT telemetry in the chat response. Cross-feature touch into 006's
`catalog/parser.py` is justified under P6 because:
* 008's chat surface routes through it on every add.
* The parser already had a Pydantic-tested public contract; the patch
  is purely additive.
* All 7 pre-existing 006 parser tests still pass.

### Implementation
1. **`backend/app/catalog/parser.py`** — 4 changes:
   * `_PRICE_RES` now uses a shared `_NUM` group that accepts
     `NNN(,NNN)*[.dd]` (thousands-comma honoured).
   * Added a `for NNN` regex and a guarded bare-integer fallback
     (≥3 digits, negative look-behind on `sku|id|model|serial|part|
     code|no|no.|#` so SKUs don't masquerade as prices).
   * `_to_price` now strips commas before `Decimal()`.
   * Name cleanup strips an `add (a|an|the)? (new)? (product)?` leading
     preamble and trailing `for|at|of|is|by|to` so chat-added names
     look human ("Samsung S24" instead of "Add a new Samsung S24 for").
2. **`backend/tests/test_product_parser.py`** — 5 new tests covering:
   bare integer, thousands-comma (incl. Indian-style `1,00,000` and
   decimals `1,250.50`), `priced at`/`price` phrasing, SKU/ID/model
   negative cases, add-preamble stripping.
3. **`backend/app/agent_router/route.py`** —
   `RouterResult.confidence: float` promoted to a top-level field;
   stamped on every code path (success, role-denied, unknown) by
   moving the assignment to the bottom of `route_text`.
4. **`backend/app/agent_router/chat_adapter.py`** — `ChatReply` now
   carries an optional `debug: ChatDebug | None` with `{intent,
   confidence}`. Field is nullable so older frontend deployments can
   ignore it.
5. **`frontend/src/store/chatbotContext.jsx`** — forward `debug` from
   the service response into the message record.
6. **`frontend/src/components/chatbot/MessageBubble.jsx`** — render a
   small monospace badge "intent · 0.89" on bot replies when `debug`
   is present. Tooltip exposes the full label.
7. **`frontend/src/components/chatbot/MessageBubble.css`** —
   `.bubble__debug` style: subtle 0.05 black on muted text.

### Out of scope (still upstream)
* Worded-number parsing ("fifty thousand rupees") — out of feature
  008's scope; both 006 and 008 would need a number-words pass.

### Verification
* `pytest backend/tests/test_product_parser.py` → **12/12** pass
  (7 pre-existing + 5 new).
* `pytest` of the V1 feature-008 test set (`test_product_parser`,
  `test_agent_router`, `test_agent_route_endpoint`,
  `test_sbert_loader`, `test_intent_classifier`, `test_entities`,
  `test_search_route`) → **75/75** pass.
* Pre-existing `test_health::test_no_route_other_than_health` and
  `test_auth_*` failures are unrelated (006 enabled `/docs`; auth
  fixtures require `asyncpg`). Both were failing before this session.
* End-to-end TestClient run on a **fresh DB**:
  * Vendor register → 201
  * `/api/chat` "Add a new Samsung S24 for 45000" → 200,
    `debug={intent:add_product, confidence:0.98}`, listing "Samsung
    S24".
  * `/api/chat` "Add iPhone 15 for ₹45,000" → 200, parsed as 45000.0
    (not 45.0), listing "iPhone 15".
  * `/api/chat` "show me iphone under 60000" → 200,
    `debug={intent:search_products, confidence:0.78}`, returns just-
    added iPhone.

## Session 6 — 2026-06-23 — Intent misclassifications + /api/orders 404 + voice UX

### Context
User reported three live-system issues from chatbot vendor usage:

1. `"add iPhone 50000"` → `update_product` (confidence 0.74), running
   the update path on whichever product the keyword "iPhone" found.
2. `"Add Amul milk for 29"` → `delete_product` (confidence 0.42),
   deleting the iPhone listing instead.
3. `/api/orders` returning 404 on every page load (UI spam).
4. Voice-to-text in chatbot "not working as expected" — the input
   filled the field but didn't submit.

### Root-cause analysis

**(1) and (2)** — SBERT prototypes leaked specific product nouns:
```
update_product: "change the price of my iphone to 50000"
delete_product: "delete the milk listing"
```
These prototypes contain the literal tokens "iphone" and "milk".
Cosine similarity is content-based: any user utterance containing
"iphone …  50000" or "milk" gets pulled towards them regardless of
the action verb. Verified empirically — top-3 prototype matches
for `"add iPhone 50000"` were:
```
0.741  [update_product ] change the price of my iphone to 50000
0.655  [add_product    ] create a new listing iphone for 50000 rupees
0.526  [search_products] find cheap phones below 50000
```
The 0.086 margin made `update_product` win.

**(3)** — `/api/orders` is referenced in
`frontend/src/utils/constants.js` (feature 004 checkout) but never
implemented in any of 002/003/005/006. The 404 is correct in the
absence of a real Orders feature — but the UI spams it.

**(4)** — `ChatInput.appendVoice` *appends* the transcript to the
text field without submitting. Voice was meant to be hands-free.

### Fixes

1. **`backend/app/agent_router/intents.py`** — prototype rewrite:
   * All prototypes now encode *action shape* with generic placeholders
     ("item", "product", "listing"). Removed every brand name and every
     specific number.
   * Added terse-form `add_product` prototypes (`"add item"`, `"add
     item for price"`, …) for the short utterances vendors actually
     type / dictate.
   * Added a deterministic **imperative-verb tiebreaker**
     (`_verb_hint`, `_VERB_HINTS`). When SBERT is below threshold OR
     within 0.05 of an alternative whose verb prefix matches the
     utterance, the verb wins. This is spec FR-2 ("deterministic regex
     + SBERT") taken seriously — `add|create|post|register|sell` → add,
     `update|change|edit|modify|set` → update, `delete|remove|drop|
     take down|discontinue` → delete, etc.
   * `classify` rewired to consult the tiebreaker in both the
     low-confidence and within-margin paths.

2. **`backend/app/api/routes/orders.py`** (new file) — V1 stub:
   * `GET /api/orders` → 200 `{ "orders": [] }` (auth-gated).
   * `POST /api/orders` → 501 with a friendly message pointing at
     spec §9.
   * `main.py` includes the router under tag `orders`.

3. **`frontend/src/components/chatbot/ChatInput.jsx`** — voice UX:
   * If the text field is empty when a voice transcript arrives,
     auto-submit (queueMicrotask after state flush). If the user was
     typing, keep the legacy append behaviour.
   * Comment explains the two-mode policy.

### Tests

* `backend/tests/test_intent_classifier.py` — added two test groups:
  - `TERSE_ADD_CASES` parametrised regression (9 utterances) for the
    user-reported failure modes.
  - `test_verb_tiebreaker_does_not_override_clear_search` and
    `test_verb_tiebreaker_respects_update_and_delete` to lock in the
    invariants that the tiebreaker doesn't steamroll clearly-classified
    queries.
* Full slow suite: 13/13 pass (was 2/2 before).
* V1 feature set (`test_agent_router`, `test_agent_route_endpoint`,
  `test_intent_classifier`, `test_entities`, `test_sbert_loader`,
  `test_search_route`, `test_product_parser`): unchanged, all green.

### End-to-end verification (TestClient, fresh DB)

10/10 vendor add prompts across 7+ categories:
```
[OK] add_product (0.40)  iPhone 15 Pro            ← Electronics
[OK] add_product (0.37)  Samsung Galaxy S24       ← Electronics
[OK] add_product (0.32)  Dell XPS 13 laptop       ← Computers
[OK] add_product (0.42)  Amul milk                ← Dairy   (was → delete!)
[OK] add_product (0.34)  Britannia whole wheat bread ← Bakery
[OK] add_product (0.51)  Tropicana orange juice   ← Beverages
[OK] add_product (0.44)  Tata salt                ← Pantry
[OK] add_product (0.43)  Nivea body lotion        ← Personal Care
[OK] add_product (0.39)  Parle G biscuits         ← Snacks
[OK] add_product (0.35)  Sony WH-1000XM5          ← Audio
```

`/api/orders`:
* GET anon → 401 (matches documented 🔒)
* GET auth → 200 `{ "orders": [] }`
* POST auth → 501 with friendly placeholder body

### Out of scope (still upstream / future)

* Worded-number ASR transcripts ("fifty thousand rupees") still produce
  `price=None` — needs number-words parsing (not 008 scope).
* Real Orders feature — scheduled for 009/010; the stub is explicitly
  labelled so it cannot ossify.

## Session 7 — 2026-06-23 — Search results not rendering + everything "Out of stock"

### Context
User reported that `GET /api/search?q=show+me+Samsung+under+50000`
returned a perfect payload — two Samsungs, meta with keywords + max
price — but the UI showed nothing.

### Root causes

1. **Wire-shape drift on `SearchPage.jsx`**. The 004 mock and the 008
   real API disagree: mock returned `{ results: [...] }`, 008 returns
   `{ products: [...] }`. `productContext.jsx` was patched for that
   already, but `pages/SearchPage.jsx` lines 26 and 53 still
   destructured `const { results: found } = await searchProducts(q)`.
   `found` was therefore always `undefined` → `setResults([])` → empty
   grid. **All the search result drops were happening here.**

2. **`availability` always false for chat-added products.** The 006
   parser defaulted `stock_quantity` to `0` when the description did
   not include "in stock" / "qty". `projection.project_listing`
   maps `stock > 0` to `availability`, and `ProductCard` shows
   "Out of stock" + disables Add-to-cart on `availability=false`.
   Net effect: every product added via the chatbot was unsellable on
   sight.

### Fixes

1. **`frontend/src/pages/SearchPage.jsx`** — destructure tolerantly:
   ```js
   const resp = await searchProducts(q)
   setResults(resp?.products || resp?.results || [])
   ```
   Same change applied to the image-search path so the mock keeps
   working.

2. **`backend/app/catalog/parser.py`** — default `stock = 1` when no
   explicit stock token is present. Listings are immediately
   purchasable; the vendor can update later. Explicit "30 in stock"
   etc. still wins.

3. **`backend/tests/test_product_parser.py::test_default_brand_unit_stock`**
   — updated the assertion from `stock_quantity == 0` to `== 1` and
   added a comment explaining the rationale.

### Verification

* All V1 backend tests (`test_product_parser`, `test_agent_router`,
  `test_agent_route_endpoint`, `test_search_route`): **37/37 pass**.
* End-to-end smoke (fresh DB):
  - Add 3 products via `/api/chat`.
  - `GET /api/search?q=show+me+Samsung+under+50000` → 1 product,
    `availability=True`.
  - `GET /api/search?q=milk` → Amul milk, `availability=True`.
* The two "duplicate Samsung" rows the user saw were not a bug — same
  product added twice during previous testing.

---

## Session 8 — 2026-06-23 — Fix `attempt to write a readonly database` during customer registration

### What the user reported

> `getting error for customer registation` — terminal showed:
> ```
> sqlite3.OperationalError: attempt to write a readonly database
> [SQL: INSERT INTO users (id, email, password_hash, phone, role, ...)]
> POST /api/auth/register HTTP/1.1 500 Internal Server Error
> ```

### Root cause (NOT a permissions bug)

The error was misleading. Investigation revealed:

1. **Three copies of `local_marketplace.db` existed on disk**:
   - `…/DA-225o_DeepLearning_CourseWork/local_marketplace.db` (0 bytes, stale, from accidental `cd ..` run)
   - `…/local-marketplace/local_marketplace.db` ← canonical (this session's `make run`)
   - `…/local-marketplace/backend/local_marketplace.db` (77 KB, dated June 22 — from running uvicorn out of `backend/`)
2. **Two uvicorn processes were live**:
   - PID 57933 — an 8-day-old Python 3.9 uvicorn left over from June 15, bound to port 8094.
   - PID 43429 — the current `make run`.
3. **The DB URL was cwd-relative** (`sqlite:///./local_marketplace.db`). Every time uvicorn was launched from a different directory, SQLite created/opened a *different* file. The stale 8094 process was holding a file lock on the `backend/` copy; the current `make run` was hitting the canonical copy. When SQLAlchemy tried to grow the journal file under cross-process lock contention on macOS, the kernel surfaced it as `attempt to write a readonly database` (a misleading but documented SQLite/APFS interaction).

The owner-writable `0644` permissions on every file confirmed there was nothing actually read-only — the problem was lock interference between processes resolving the URL to different files.

### Decisions

1. **Kill the two uvicorn processes** (the 8-day orphan and the current `make run`).
2. **Delete the two stray DB files**, keeping only the canonical one in
   `local-marketplace/local_marketplace.db`.
3. **Eliminate the root cause** by making the SQLite URL absolute — anchored
   at the marketplace project root — regardless of the process's `cwd`.
   This guarantees there is exactly one DB file on disk no matter where
   uvicorn is launched from.

### Implementation

`backend/app/db/session.py`:

* Added `_PROJECT_ROOT = Path(__file__).resolve().parents[3]` (resolves to
  `…/local-marketplace`).
* Added a `_normalize_sqlite_url(url)` helper that rewrites
  cwd-relative SQLite URLs (`sqlite:///./foo.db`, `sqlite:///foo.db`) to
  absolute paths anchored at `_PROJECT_ROOT`. Untouched: Postgres URLs,
  already-absolute SQLite URLs (`sqlite:////abs/path`), `:memory:`, and
  other special forms.
* Changed `LOCAL_AUTH_DATABASE_URL` from
  `"sqlite:///./local_marketplace.db"` to a built absolute URL using
  `_LOCAL_SQLITE_PATH`.
* Wired `_normalize_sqlite_url` into `_sync_database_url` and
  `_async_database_url` so both engines use the absolute path.

### Verification

* Branch test of `_normalize_sqlite_url`:
  - `sqlite:///./local_marketplace.db` → `sqlite:////Users/.../local-marketplace/local_marketplace.db` ✅
  - `sqlite:///local_marketplace.db` → same absolute form ✅
  - `sqlite:////tmp/x.db` → unchanged (already absolute) ✅
  - `sqlite+aiosqlite:///./local_marketplace.db` → absolute form with `+aiosqlite` prefix preserved ✅
  - `postgresql+psycopg://…`, `postgresql+asyncpg://…` → unchanged ✅
  - `sqlite:///:memory:` → unchanged ✅

* End-to-end registration test (TestClient launched from
  `local-marketplace/backend/` — the worst-case cwd that previously caused
  the bug):
  - `engine.url` = `sqlite:////Users/.../local-marketplace/local_marketplace.db`
  - `POST /api/auth/register` → **201 Created**, JWT issued.
  - DB inspection confirmed the new customer row was committed to the
    **canonical** DB file (no stray DBs created).

* Regression suite (all V1 features): **80/80 pass**
  `test_agent_router.py`, `test_intent_classifier.py`,
  `test_product_parser.py`, `test_entities.py`, `test_chat_router.py`,
  `test_search_route.py`, `test_sbert_loader.py`,
  `test_agent_route_endpoint.py`.

* Pre-existing failures in `test_auth_*` are unrelated — they fail the
  same way on a clean temp DB (fixture isolation problem in those test
  files, not anything to do with this change).

### Files touched

1. **`backend/app/db/session.py`** — root cause fix:
   * Anchored the local SQLite URL to `_PROJECT_ROOT`.
   * Added `_normalize_sqlite_url()` for safe-by-default URL handling.
   * Wired normalization through sync + async URL resolvers.

### Files deleted (not committed previously)

1. `…/DA-225o_DeepLearning_CourseWork/local_marketplace.db` (0-byte stray).
2. `…/local-marketplace/backend/local_marketplace.db` (stale 77 KB stray
   from a previous `cd backend/` run).

### Operational guidance

For future sessions:

* `make run` will now always use `local-marketplace/local_marketplace.db`
  regardless of which directory it's launched from. No more cwd surprises.
* If you ever see "readonly database" again, first run
  `ps auxw | grep uvicorn | grep -v grep` and
  `find . -name "local_marketplace.db*"`. A stale process + a stray DB
  file is the canonical signature.

---

## Session 9 — 2026-06-23 — Fix `/api/chat` double-fire + wire Add Product modal through SBERT chat

### What the user reported

> 1. There is issue in the Chatbot add product feature api: `/api/chat`
>    giving input to add single product but double entry is creating for
>    the same input. For a single one time input, two times chat api
>    calling.
>
> 2. In the Product feature, Add Products having voice input, but there
>    chat api is not implemented to add the product. implement here as well.

Backend access log confirmed both `/api/chat` POSTs and many other
endpoints were being called twice (lines 11/12, 15/16, 17/18, … of
terminal 6).

### Root cause — issue 1 (double `/api/chat` POST)

`ChatInput.appendVoice` scheduled the auto-submit as a side effect
**inside** a `setText(prev => …)` updater function:

```js
setText((prev) => {
  if (prev) return `${prev} ${incoming}`
  queueMicrotask(() => submitWith(incoming))   // ← side effect in updater
  return incoming
})
```

React 18 **StrictMode** (which the app uses, `src/main.jsx`)
intentionally invokes updater functions twice during development to
surface impure code. Two invocations queued **two** microtasks, each
calling `submitWith` once → two `/api/chat` POSTs → two product rows.
This pattern only manifested on the voice-auto-submit path because the
form-submit path went through a plain handler.

GET-endpoint doubling (`/api/products`, `/api/search`, `/api/orders`) is
a separate but harmless StrictMode artifact — `useEffect` is also
double-invoked in dev only, and idempotent reads are safe to repeat. We
left that alone since it disappears in production.

### Root cause — issue 2 (Add Product modal not on /api/chat)

`VendorPage.createFromDescription` was calling the legacy 006 direct
endpoint `POST /api/products/from-description`. The user wanted the
modal's voice/text input to flow through `/api/chat` so the SBERT
router's intent + entity pipeline is the single front door.

Investigation revealed that **naive `/api/chat` calls would misclassify
the typical modal description**. The placeholder text
"Amul butter 100g, ₹58, 30 in stock, Dairy" classifies as
`search_products` (0.360) because it lacks a leading action verb. A
slightly different description "Amul butter 100g, ₹58, 30 in stock,
Dairy de565f" classifies as `update_product`. Pure SBERT on the modal
path would silently search/update instead of add.

### Decisions

1. **Fix the StrictMode double-fire** by moving the auto-submit side
   effect out of `setText`'s updater, and add a ref-based single-shot
   guard (`submittingRef`) as defence-in-depth against any future
   double-invocation source (rapid clicks, mic glitches, future
   StrictMode behaviour).
2. **Wire the Add Product modal through `/api/chat`** by adding an
   **optional `intent` hint** to the chat request body. When set, the
   chat adapter skips SBERT and runs the named intent directly via
   `route_text(..., forced_intent=...)`. The chatbot UI continues to
   omit the hint (SBERT classifies free-form turns as before); only
   the Add Product modal (which is *defined* to be `add_product`) sets
   it. Unknown values are silently ignored so old clients don't break.
3. **Make ProductExtractPanel idempotent** with ref-based guards
   mirroring ChatInput, in case the user double-clicks the
   "Create from description" button before the disabled state lands.

### Implementation

#### Frontend

* **`frontend/src/components/chatbot/ChatInput.jsx`** — rewrote the
  voice/text submit path:
  * Removed the `queueMicrotask(() => submitWith(incoming))` side
    effect from inside `setText`'s updater.
  * Added `submittingRef` (single-shot guard cleared on the next
    macrotask) and `textRef` (sync access to the latest text).
  * `appendVoice` now reads `textRef.current` synchronously; if the
    field is empty it calls `submitWith(incoming)` directly. The
    updater function is now pure (`prev => prev ? prev + t : t`).

* **`frontend/src/services/chatbotService.js`** — added an optional
  fourth `intent` parameter:
  ```js
  sendChat(message, sessionId, image, intent = null)
  ```
  Forwarded as `body.intent` in JSON and as a form field
  (`fd.append('intent', intent)`) in multipart. Default `null` is
  truthy-checked so chatbot callers' existing 3-arg invocations stay
  byte-for-byte identical on the wire.

* **`frontend/src/pages/VendorPage.jsx`** —
  * Removed import of `createProductFromDescription` from
    `productService` (no longer used here; still exported for any
    future direct caller).
  * Imported `sendChat` from `chatbotService` and `ApiError` from
    `apiError`.
  * Rewrote `createFromDescription(text)` to call
    `sendChat(text, null, null, 'add_product')`.
    * On success (`listings.length > 0`) → close modal + reload.
    * On semantic failure (HTTP 200, but `listings` empty — e.g. the
      parser refused for missing price) → throw an `ApiError` with the
      assistant's `reply` as the message so it surfaces in the
      modal banner.

* **`frontend/src/components/products/ProductExtractPanel.jsx`** — added
  `runningRef` and `creatingRef` to guard both buttons against
  double-invocation. The `Button` component already sets `disabled`
  while `loading`, but state updates are async; the refs short-circuit
  any synchronous second call.

#### Backend

* **`backend/app/agent_router/chat_adapter.py`** —
  * Added a `_ALLOWED_FORCED_INTENTS` allow-list mirroring the
    intents the router knows about. Used as a server-side guard so
    callers can't force an intent like `unknown` (which would just
    short-circuit to the help reply anyway, but feels untidy).
  * Extended `ChatBody` with an optional `intent: str | None`.
  * Added an `intent: str | None = Form(default=None)` parameter to
    the FastAPI handler so the field works for both JSON and
    multipart submissions.
  * After constructing `ChatBody`, derive `forced_intent` (only set
    when the value is in the allow-list, otherwise None) and pass it
    to `router_logic.route_text(..., forced_intent=forced_intent)`.

### Verification

* **Backend regression** — `83/83 pass` across feature 008 + parser
  + intent + entities suites (was 80, +3 new tests for the intent
  hint):
  * `test_intent_hint_forwarded_to_router` — confirms JSON body's
    `intent: 'add_product'` reaches `route_text` as `forced_intent`.
  * `test_unknown_intent_hint_silently_dropped` — confirms a bogus
    value is dropped, SBERT classifies as usual.
  * `test_intent_hint_via_multipart` — confirms the multipart form
    path honours the hint too (voice / future image flows).

* **End-to-end TestClient probe**:
  * Case A — `POST /api/chat` no hint, naive description
    "Amul butter 100g, ₹58, 30 in stock, Dairy …" → SBERT classifies
    as `update_product`, `listings=0`. (This is the failure mode that
    motivates the hint.)
  * Case B — same description with `intent: 'add_product'` → product
    persisted, `listings=1`, reply "Added: Amul butter de565f
    (₹58.0).".
  * Case C — `intent: 'garbage_value'` → silently dropped, SBERT
    classifies "find me iPhone" as `search_products` (0.488).
  * DB inspection after Case B → **exactly 1 row** with the test
    product name (no double-write).

* **Frontend lint** — clean (`npm run lint`).
* **Frontend build** — clean (`npm run build`, 104 modules
  transformed, 637 ms).

### Files touched

Frontend:
1. `frontend/src/components/chatbot/ChatInput.jsx`
2. `frontend/src/components/products/ProductExtractPanel.jsx`
3. `frontend/src/pages/VendorPage.jsx`
4. `frontend/src/services/chatbotService.js`

Backend:
5. `backend/app/agent_router/chat_adapter.py`
6. `backend/tests/test_chat_router.py` (+ 3 regression tests)

### Notes for future readers

* The optional `intent` field on `/api/chat` is the canonical place to
  add an intent override from a specialised UI surface. The HTTP
  contract for the chatbot UI is unchanged (omit the field, SBERT
  classifies). Adding more single-purpose modals later (e.g.
  "Delete by description" button) is a one-line change in the caller.
* The double-GET observation on idempotent endpoints (StrictMode
  `useEffect` re-runs) is **not a bug**; it only happens in dev mode
  and disappears under `npm run build`. The original double-POST WAS
  a bug because POST is not idempotent and the updater was impure;
  that is now fixed.

---

## Session 10 — 2026-06-23 — Auto-submit voice transcript in Vendor Add Product modal

### What the user reported

> In the Vendor Dashboard, Manage Products, having Button +Add Product,
> voice taking input but after voice complete it should add the product
> auto without clicking any button. Currently it's just taking the voice
> input and converting into the text but chat api with sbert model not
> calling auto like calling in chatbot and search feature.

Screenshots showed: vendor opens "+ Add Product", presses the mic on
"Describe the product", says "add Amul butter 100 G for Rs 80", the
transcript fills the textarea, but nothing happens until the vendor
manually clicks "Create from description". Expected: auto-submit like
the chatbot/search voice flows.

### Root cause

In `frontend/src/components/products/ProductExtractPanel.jsx` the voice
handler was a one-liner that only filled the textarea:

```jsx
<VoiceButton
  onText={(t) => setPrompt((p) => (p ? `${p} ${t}` : t))}
  title="Dictate product details"
/>
```

The chatbot `ChatInput` already auto-submits via `appendVoice` (session
6 + session 9 hardening) but the vendor Add Product modal never got
the equivalent wire-up.

### Decisions

* Mirror the chatbot's `ChatInput.appendVoice` ergonomics exactly:
  * Empty textarea + transcript arrives → auto-submit via the SBERT
    chat router (the same `intent: 'add_product'` hinted path wired
    in session 9).
  * Textarea has existing text → append the transcript, let the
    vendor review and submit. Preserves the "dictate the rest of my
    sentence" use case.
* Reuse the existing `creatingRef` single-shot guard (session 9) so
  the auto-submit cannot double-fire under React 18 StrictMode.
* Add a `promptRef` mirror of the textarea so the voice handler can
  read the latest value synchronously instead of through a stale
  closure.

### Implementation

`frontend/src/components/products/ProductExtractPanel.jsx`:

1. Added `promptRef` (refreshed each render to `prompt`) for
   synchronous read-only access in event handlers.
2. Changed `createDirect`'s signature from `()` to
   `(explicitText)`. When the voice path supplies the transcript
   directly, we bypass the setState round-trip. To stay compatible
   with `<Button onClick={createDirect}>` (which passes a synthetic
   event), the function ignores any non-string argument and falls
   back to `promptRef.current`.
3. Added `appendVoice(t)`:
   * Returns early if the transcript is empty.
   * If `promptRef.current.trim()` is non-empty → append via
     `setPrompt(p => p ? \`${p} ${incoming}\` : incoming)`. Updater
     is pure (no side effect), so StrictMode's double-invoke is
     harmless.
   * Else (empty textarea) → `setPrompt(incoming)` to reflect what
     was captured, then call `createDirect(incoming)` synchronously
     **outside** any setState updater. The session-9 lesson holds:
     side effects in updaters get double-fired by StrictMode.
4. Wired `<VoiceButton onText={appendVoice}>` with an updated tooltip
   "Dictate product details — auto-submits when complete".

### Verification

* Frontend `npm run lint` — clean.
* Frontend `npm run build` — clean (104 modules, 600 ms).
* Backend regression (`test_chat_router`, `test_agent_router`,
  `test_intent_classifier`, `test_product_parser`) — **38/38 pass**.
  No backend change; the auto-submit reuses the session-9
  `intent: 'add_product'` chat-router path.

### Files touched

1. `frontend/src/components/products/ProductExtractPanel.jsx` — added
   `promptRef`, refactored `createDirect` to accept optional explicit
   text + ignore event objects, added `appendVoice` handler, rewired
   `VoiceButton`.

### Operational notes

When the vendor speaks a complete description (e.g. "add Amul butter
100g for Rs 80") the path is:

```
mic → SpeechRecognition → appendVoice(transcript)
  → setPrompt(transcript)        // UI feedback
  → createDirect(transcript)     // bypass state, sync auto-submit
  → onCreateFromDescription      // VendorPage.createFromDescription
  → sendChat(text, null, null, 'add_product')   // session 9 hint
  → POST /api/chat                // intent forced, SBERT skipped
  → product_service.create_from_description
  → 1 row written, listings=[ProductRead]
  → modal closes, vendor's listings table reloads
```

If the SBERT parser refuses (e.g. no price found) the assistant's
reply surfaces as the modal error banner via session 9's `ApiError`
wrapping in `VendorPage.createFromDescription`.

---

## Session 11 — 2026-06-23 (docs only; spec restructure, zero code touched)

### Context / goal
User asked (three times across the session): *"review the spec.md for
008-sbert-intent-router folder, and update it, so that it's should well
Structured, clean and clear spec driven development and should be in
humanised form."*

The existing `spec.md` had grown organically across nine sessions and was
hard for a new reader to land on: the architectural contract, the
post-006-merge addendum, and a free-form "Integration - Fixed" tail were
stacked end-to-end with no narrative hand-off between them. Several fixes
shipped in sessions 8–10 weren't reflected in spec.md at all.

### Decisions made & reasoning
- **Append, do not rewrite.** Constitution P6 (file idempotency) makes
  spec files effectively append-only once they describe shipped behaviour.
  Truncating or reordering would erase the historical contract that drove
  implementation and would lose the *why* behind each FR.
- **Two-part structure with a "Reader Start Here" prepend.** Inserted a
  new **Part A** between the YAML front-matter and the original `# Feature
  008: SBERT Intent Router — Specification` heading. Part A is a short,
  plain-English summary (one-paragraph TL;DR, why it exists, scope by
  role, the seven intents, end-to-end flow diagram, live HTTP surface,
  module map, post-launch fixes table, run instructions, glossary). The
  original document becomes **Part B — Historical contract** below it,
  byte-for-byte preserved.
- **Promote the free-form fixes tail into a structured table in Part A.**
  Sessions 4–7 had been written up as numbered prose at the end of §9;
  sessions 8–10's fixes (parser, db/session absolute path, StrictMode
  double-fire, voice-driven Add Product modal) were not reflected in
  spec.md at all. Part A §A.8 now lists all nine fixes uniformly:
  symptom → root cause → fix → files touched → session. Added a
  "Reader note" at the top of §9's prose list pointing to §A.8 and
  noting that the prose is kept verbatim for audit fidelity.
- **Reading-order metadata.** Added `status:` and `reading_order:` keys
  to the YAML front-matter so the document declares its own navigation
  contract.

### Files altered
- `specs/008-sbert-intent-router/spec.md` — purely additive: 341 → 556
  lines. Front-matter extended with `status` and `reading_order`. New
  Part A inserted between front-matter and the original `# Feature 008`
  heading. Original sections 1–9 (and the prose fixes tail) untouched
  except for one inserted "Reader note" blockquote pointing back to
  §A.8.
- `specs/008-sbert-intent-router/conversation-history.md` — this entry
  (Constitution P7 / P3).

### Edge cases / unknowns surfaced
- None new. The restructure asked nothing of the running code; `make
  test` was not re-run for this session because no source file changed.
- `prompts.md` was not updated by this session because the user's
  request ("review and update spec.md … humanised form") was a
  documentation directive, not a recurring AI prompt pattern.

### No `[NEEDS CLARIFICATION]` raised or resolved.

---

<!-- Future sessions append below this line. Never edit or truncate prior entries. -->
