# Feature 008: SBERT Intent Router — Implementation Plan

> **Status (2026-06-23):** Shipped. M1–M8 complete, nine post-launch fixes
> landed on top.
> **Constitution P1:** 
> implementation file was created. It is a dry-run by design — each
> milestone names the exact files, the order, and the verification step —
> and is kept verbatim per **P3 (audit trail)** and **P6 (append-only)**.

---

## How to read this document

This plan is split into two parts:

1. **Part A — Reader Start Here.** Plain-English answers to "What did we
   plan?", "Did we ship it?", "What changed after?", and "Where do I look
   for X?" Read this first if you just landed on the repo.
2. **Part B — Original dry-run plan (M1–M8).** The approved pre-flight
   plan from 2026-06-23, preserved byte-for-byte. Read this when you need
   to know *what we promised* before the first line of code was written —
   it remains the diff target for "did we do what we said we would?".

The two parts agree. Where Part B says "stub", Part A and the spec §9
addendum note that the stub was replaced by the real Feature 006 service
on cutover day.

---

# Part A — Reader Start Here

## A.1 One-paragraph summary

This plan turned the Feature 008 spec into a sequenced, eight-milestone
build. The order was deliberate: **build the call target first**
(products stub, M1), **then the brain** (SBERT + intent classifier,
entity extractors, router, M2–M4), **then the HTTP surfaces**
(M5), **then the frontend wire-up and the audit/build glue** (M6–M8).
Each milestone had its own "Verify" gate — if a milestone's tests didn't
go green, the next one didn't start. Everything was approved before
any source file was touched (Constitution P1).

## A.2 What the plan covered (one line each)

| Milestone | What it built                              | Verify gate (then)                              |
| :-------- | :----------------------------------------- | :---------------------------------------------- |
| **M1**    | In-memory products + catalog stub          | `pytest test_products_stub.py` + curl smoke     |
| **M2**    | SBERT loader + intent classifier           | Loader behaviour + ≥0.9 accuracy on 30 prompts  |
| **M3**    | Regex/SBERT entity extractors              | Parametrised `test_entities.py`                 |
| **M4**    | Router `route_text(intent, entities, role)`| Per-intent round-trip + role-gate test          |
| **M5**    | HTTP surfaces (`/api/chat`, `/api/agent/route`, `/api/search`) + `main.py` wiring | Boot test + endpoint contract tests            |
| **M6**    | Frontend wire-up (search, agent service)   | `npm test` + manual search smoke                |
| **M7**    | `.env.example`, `pyproject.toml`, `Makefile`, docs | Lint clean, build clean                  |
| **M8**    | Audit close (conv-history + final ruff)    | `git diff --stat backend/agent/ ⇒ empty`        |

Full details, file lists, and the exact "Verify" assertions are in
**Part B §2** below — that's the authoritative pre-flight plan and was
never edited after approval.

## A.3 What actually shipped (delta vs. plan)

| Area                       | Planned in Part B                                  | Shipped                                                                                          |
| :------------------------- | :------------------------------------------------- | :----------------------------------------------------------------------------------------------- |
| Products data path (M1)    | In-memory `backend/app/products_stub/`             | Replaced by real Feature 006 service (SQLAlchemy / SQLite locally). Cutover documented in spec §9. |
| ORM models                 | Not in scope — Part B explicitly says "no migrations" | Three model files authored to fill a 006 upstream gap (`backend/app/models/{category,product,subcategory}.py`). |
| SBERT pieces (M2–M4)       | Loader, intent classifier, entities, router        | Shipped as planned. Plus: a deterministic imperative-verb tiebreaker layered on top of SBERT (added in Session 6 after dogfood found `"add iPhone 50000"` misclassifying). |
| HTTP surfaces (M5)         | `/api/chat`, `/api/agent/route`, `/api/search`     | All three shipped. Plus: `/api/orders` stub added in Session 6 to silence frontend 404s.          |
| `/api/chat` contract       | `{message, sessionId}` → `{reply, listings, sessionId}` | Same shape, but extended with an **optional** `intent` field on the request to let specific UI flows (Add-Product modal) bypass classification. Backward compatible. |
| Frontend (M6)              | Read `{products}` from search; `agentService.js`   | Shipped. Plus reads tolerate both `{products}` and `{results}` shapes; the chatbot surfaces an SBERT debug badge; voice auto-submit added in Sessions 6/9/10 with StrictMode-safe guards. |
| Docs/env/build (M7)        | `.env.example`, `pyproject.toml`, `Makefile`, README, architecture | Shipped. `make sbert-test` accuracy gate deferred because the corporate proxy blocks huggingface.co — gate is wired and triggers once `make sbert-download` runs on an open network. |
| Audit close (M8)           | One session entry in conv-history                  | Sessions 2–11 in conv-history; P-1 through P-6 in prompts.md; spec gained a Part A reader view; this plan now has Part A too. |
| Files-not-touched audit    | `backend/agent/` + `local-marketplace2/` untouched | Held. Verified by `git diff --stat`.                                                              |

## A.4 Build order — visualised

```
M1  products stub                ── the call target (built first so the brain has somewhere to call)
│
├─ M2  SBERT loader + classifier  ──┐
│
├─ M3  entity extractors            ├─ the brain
│
├─ M4  router dispatch            ──┘
│
├─ M5  HTTP adapters             ── the wire
│      /api/chat   /api/agent/route   /api/search   + main.py wiring
│
├─ M6  frontend wire-up
│
├─ M7  env / build / docs
│
└─ M8  audit close + ruff sweep
```

Every milestone's "Verify" step was a gate. M1 had to be green before
M2 started; M2 before M3; and so on. This was the cheap insurance that
let us approve the whole plan up-front and run it without per-step
re-approval.

## A.5 Key conventions (carried over from sibling features)

These weren't novel to Feature 008 — they were *reused* deliberately so
nothing here is a surprise to readers of Features 002/003/007:

- **JWT auth.** Same `Authorization: Bearer <jwt>` extraction path.
- **DB session.** `backend/app/db/session.SessionLocal` (sync); after the
  006 cutover this points at real SQLAlchemy, not the in-memory stub.
- **Lifespan warming.** SBERT model + intent-prototype embeddings are
  pre-computed once at FastAPI startup so per-request latency stays low.
- **`lru_cache(1)` singletons** with explicit `reset_*_cache()` test
  hooks — mirrors Feature 007's `_get_orchestrator` pattern.
- **Pydantic** with `ConfigDict(extra="ignore", str_strip_whitespace=True)`.

## A.6 Sibling-doc cross-reference

If you're looking for something specific, here's where it lives:

| Looking for...                                       | Read this                                   |
| :--------------------------------------------------- | :------------------------------------------ |
| Plain-English description of what the agent does     | `spec.md` → Part A                          |
| The seven intents + role gating + final HTTP calls   | `spec.md` → §A.4 (table) and §2 (FR-1, FR-4) |
| End-to-end flow diagram (frontend → backend → DB)    | `spec.md` → §A.5                            |
| List of every post-launch fix with root cause + files | `spec.md` → §A.8 (table)                    |
| The original architectural contract + acceptance bars | `spec.md` → Part B (§§1–8)                  |
| The 006-cutover delta                                | `spec.md` → §9 addendum                     |
| **The build order, file-by-file, with verify gates**  | **This file → Part B §2 (M1–M8)**          |
| The chronological narrative of every working session  | `conversation-history.md` (Sessions 1–11)   |
| The user-driven prompt arcs that produced artifacts   | `prompts.md` (P-1 .. P-6 + recurrence table) |

## A.7 Risks predicted vs. risks that actually bit

The original Part B §4 named four risks. Reality:

| Predicted risk                                    | Did it bite? | Notes                                                                                                                                  |
| :------------------------------------------------ | :----------- | :------------------------------------------------------------------------------------------------------------------------------------- |
| First-time SBERT download fails behind a firewall | **Yes**      | `make sbert-test` accuracy gate deferred (Session 2). Pre-download workflow held up; loader fails fast and clearly when the model is absent. |
| Cold model load slows CI / dev reload             | **No**       | `lru_cache(1)` + lazy build kept CI under budget; tests stub the loader.                                                              |
| Intent prototypes drift from real user phrasing   | **Yes — once** | Terse imperatives (`"add iPhone 50000"`) misclassified. Fixed in Session 6 with generic prototypes + an imperative-verb tiebreaker.   |
| Stub diverges from eventual real 006              | **No**       | Cutover (Session 3) replaced the stub cleanly; only a parser gap on the 006 side surfaced as fallout, fixed in Session 8.             |

**Unpredicted risks that did bite** (all fixed):

- React 18 StrictMode double-invocation of `setState` updater functions
  with embedded side-effects → duplicate `POST /api/chat` calls. Fixed
  in Session 9 by moving the side-effect outside the updater + a
  `submittingRef` guard.
- `cwd`-relative SQLite path → stray DB files → "readonly database"
  errors on macOS/APFS lock contention. Fixed in Session 8 by making
  the path absolute and anchored to the project root.
- 006's catalog parser rejected bare numbers, thousands separators,
  and mis-parsed SKU-style tokens as prices. Fixed in Session 8 by
  rewriting the price regex + adding a negative look-behind for SKUs.

Lesson learnt: **plan for the model-download cliff and the
StrictMode/concurrency cliff**. Both are recurring across React +
Python ML projects and would benefit from reusable skills (already
flagged as `[SKILL CANDIDATE]` in `prompts.md`).

## A.8 Glossary (plan-specific)

- **Dry-run.** A plan that names every file it will create or touch and
  every test it will run, with zero source files modified, written for
  user approval *before* implementation starts. Per Constitution P1.
- **Verify gate.** A test (or `curl` smoke) that must pass before the
  next milestone begins. Acts as a per-step rollback boundary.
- **One-line rollback.** The promise that the entire feature's HTTP
  wiring can be reverted by removing the four `app.include_router(...)`
  lines added in `main.py` (or, more crudely, by re-instating the
  Feature 002 `chat_router` import). Used as a safety net during M5.
- **`# STUB-006` tag.** Code comment marker on every line that should
  disappear when the real Feature 006 lands. Made the cutover (Session
  3) mechanical.

---

# Part B — Original dry-run plan (M1–M8)

> Everything below this line is the dry-run plan that was approved on
> 2026-06-23 before any implementation file was touched. Kept verbatim
> per Constitution P3 (audit trail) and P6 (append-only). Use it as the
> diff target when reviewing "did we ship what we promised?".

# Feature 008: SBERT Intent Router — Implementation Plan (Dry-Run)

> Constitution P1: this plan MUST be **user-approved** before any implementation
> file is created or modified. It is a dry-run: each milestone names the exact
> files, the order, and the verification step.

## 0. Resolved decisions (from 2026-06-23 Q&A — six picks, two follow-ups)

| Q | Decision |
| :-- | :-- |
| Q1 — replace or coexist | **Replace.** `/api/chat` is rewired to the new SBERT router; feature 002 modules stay in-tree but are unreachable on the wire. Rollback = 1 line in `main.py`. |
| Q2 — products API source | **Stub.** Local in-memory stub in this repo, byte-compatible with the 006 REST contract. |
| Q3 — intents in v1 | **Six** named intents + `unknown` fallback: `search_products`, `add_product`, `update_product`, `delete_product`, `get_my_listings`, `get_categories`. |
| Q4 — entity extraction | **Regex (price/ID/keywords) + SBERT for category**. No LLM in the request path. |
| Q5 — SBERT model | `sentence-transformers/all-MiniLM-L6-v2` — 80 MB, English, CPU. |
| Q6 — feature slot | `008-sbert-intent-router`. |
| Q7 — search filters | **Richer stub** — `?q=`, `?max_price=`, `?min_price=`, `?category=`, `?vendor_id=` on `GET /api/products`. |
| Q8 — frontend endpoint | **Reuse `/api/chat`** (existing chatbot path) **and add `POST /api/agent/route`** for one-shot search-bar / programmatic use. |

## 1. Conventions reused (no new abstractions)

- **Auth.** Same `Authorization: Bearer <jwt>` extraction as feature 003 / 007. We import `auth_service.get_current_user(db, token)` directly; no new dependency tree.
- **DB session.** Reuse `backend/app/db/session.SessionLocal` for the products stub *only* because the stub stores its dict on `app.state` — no real ORM rows, no migrations. (The real 006 will own migrations.)
- **Lifespan pattern.** SBERT model + intent embeddings are warmed inside a single `@app.on_event("startup")` (or FastAPI `lifespan`) — same shape feature 007 uses for the orchestrator singleton.
- **lru_cache singletons.** Same trick feature 007 uses for `_get_orchestrator` — `_get_sbert()`, `_get_intent_index()`, `_get_products_stub_state()`. All exposed via `reset_*_cache()` test hooks.
- **Pydantic schemas.** Mirror feature 007 conventions (`ConfigDict(extra="ignore", str_strip_whitespace=True)`).
- **Project layout.** New top-level packages live under `backend/app/`: `agent_router/`, `products_stub/`. No `__init__.py` exports that aren't strictly used.

## 2. Milestones (build order — STRICTLY sequential within a milestone, the milestones themselves are also sequential)

### M1 — Products stub (the call target)

Build this **first** because the rest of the feature has nothing to call until it exists.

- `backend/app/products_stub/__init__.py` → re-exports `router` (the FastAPI router).
- `backend/app/products_stub/schemas.py` → Pydantic models mirroring `local-marketplace2/.../schemas/product.py` (`ProductRead`, `ProductCreate`, `ProductUpdate`, `ProductDescriptionRequest`, `ProductResponse`, `ProductListResponse`, `CategoryRead`, `SubCategoryRead`). Verbatim field shapes; `UnitType` enum re-declared locally.
- `backend/app/products_stub/store.py` → in-memory store:
  - `class ProductsStore`: dict-of-products keyed by `product_id` + dict of categories/subcategories. Seeded at construction with 8–12 products spanning the 005 categories and 2 fake vendors. Idempotent `seed_if_empty()`.
  - `_score_by_description(text, products) -> Product` mirrors 006 FR-9 heuristic (lowercase, tokenize, count overlap on name+brand+description). Ties broken by `created_at`.
  - `_filter(query: ProductQuery) -> list[Product]` applies the FR-9 extra query params (q substring on name/brand/description, max/min price, category match, vendor scope).
- `backend/app/products_stub/parser.py` → minimal description → fields parser. Tagged `# STUB-006`. Extracts `price` (regex), assigns `brand="Generic"`, `unit_type=PIECE`, `unit_value=1`, `stock_quantity=0`. Raises if no price. (We do *not* reproduce 006's full parser — just enough to satisfy the success criteria.)
- `backend/app/products_stub/router.py` → FastAPI router mounting:
  - `GET /api/products` (with `vendor_id`, `q`, `max_price`, `min_price`, `category` params)
  - `POST /api/products` (vendor JWT required)
  - `POST /api/products/from-description` (vendor JWT required)
  - `POST /api/products/delete-by-description` (vendor JWT required)
  - `PUT /api/products/{product_id}` (vendor JWT required)
  - `DELETE /api/products/{product_id}` (vendor JWT required, 204)
  - `GET /api/catalog/categories`, `GET /api/catalog/subcategories`
- **Verify (M1):**
  - `pytest backend/tests/test_products_stub.py` covers: list (no filter), list with each query param, create from description happy + no-price-rejected, update, delete by id, delete by description (hit + miss), category list.
  - `curl http://localhost:8000/api/products` returns 8–12 seeded rows.

### M2 — SBERT loader + intent classifier

- `backend/app/agent_router/__init__.py` → empty (exports happen at sub-module level).
- `backend/app/agent_router/sbert.py`:
  - `def get_sbert_model() -> SentenceTransformer` — `lru_cache(1)`. Honours `MODELS_DIR`/`ALLOW_MODEL_DOWNLOAD` per FR-12.
  - `def reset_sbert_cache() -> None`.
- `backend/app/agent_router/intents.py`:
  - `INTENT_PROTOTYPES: dict[str, list[str]]` — ≥ 3 paraphrases per intent. Frozen as data; no runtime dependency.
  - `class IntentIndex` holding the matrix of prototype embeddings.
  - `def get_intent_index() -> IntentIndex` — `lru_cache(1)`. Built lazily on first call.
  - `def classify(text: str) -> tuple[str, float]` — returns `(label, score)`. Below `INTENT_CONFIDENCE_THRESHOLD` → `("unknown", score)`.
- `backend/app/core/config.py` → append `INTENT_CONFIDENCE_THRESHOLD: float = 0.45`, `CATEGORY_MATCH_THRESHOLD: float = 0.55`, `MODELS_DIR: str = "./models/sbert"`, `ALLOW_MODEL_DOWNLOAD: bool = False`. (Append only — feature 007 entries untouched.)
- **Verify (M2):**
  - `pytest backend/tests/test_sbert_loader.py` — model loads from `MODELS_DIR` if present; fails fast with a useful message when neither path nor download is allowed.
  - `pytest backend/tests/test_intent_classifier.py` — 30-utterance suite (5 per labelled intent + 5 distractors); accuracy assertion ≥ 0.9 with the default threshold.

### M3 — Entity extractors

- `backend/app/agent_router/entities.py`:
  - `extract_price(text) -> float | None` — regex over `₹|Rs\.?|INR\s?` prefixes, comma forms, `k`/`K` shorthand. Documented with examples in docstring.
  - `extract_product_id(text) -> str | None` — looks for `id 12345`, `#12345`, `product 12345`, or a bare UUID. Returns string form.
  - `extract_keywords(text, intent) -> str` — strips intent-trigger verbs (`show`, `find`, `add`, `delete`, `update`, etc.) and stop-words, returns the residue (used as `q` in search).
  - `extract_category(text) -> tuple[str, float] | None` — embeds `text` and the seeded category names; returns highest match above `CATEGORY_MATCH_THRESHOLD`.
- **Verify (M3):**
  - `pytest backend/tests/test_entities.py` — parametrised table of inputs + expected outputs for each extractor.

### M4 — The router (intent + entities → API call)

- `backend/app/agent_router/route.py`:
  - `class RouterResult(BaseModel)` — `intent, entities, reply, listings, api_called, api_status, meta`.
  - `def route_text(text: str, role: str, vendor_id: str | None, db) -> RouterResult`:
    1. `intent, score = classify(text)`.
    2. Role gate per FR-4 (`unknown` allowed; `add/update/delete/get_my_listings` vendor-only).
    3. Entity extraction per FR-3.
    4. Dispatch via match-case on `intent`:
       - `search_products` → call `products_stub.store.list_products(query)` directly (in-process — no HTTP self-call; faster + simpler).
       - `add_product` → call `products_stub.store.create_from_description(vendor_id, text)`.
       - `update_product` → if no `product_id`, attempt the single-candidate vendor-scoped lookup (Scenario 4 edge case); else `update_product(...)`.
       - `delete_product` → `delete_by_description(vendor_id, text)` (uses 006 FR-9 heuristic in the stub).
       - `get_my_listings` → `list_products(vendor_id=vendor_id)`.
       - `get_categories` → `list_categories()`.
       - `unknown` → polite reply, no call.
    5. Project results to `Listing` shape (FR-10) for any `listings` field.
- `backend/app/agent_router/projection.py` — single `_project_listing(row) -> Listing` (small file; lives separately to be reusable from chat/search adapters too).
- **Verify (M4):**
  - `pytest backend/tests/test_agent_router.py` — round-trips for each of the 6 intents + `unknown`; role-gating test; "no product_id, single match" disambiguation test.

### M5 — HTTP surfaces

- `backend/app/agent_router/api.py` → `router = APIRouter()`, `POST /api/agent/route` per FR-6.
- `backend/app/agent_router/chat_adapter.py` → `router = APIRouter()`, `POST /api/chat`. Re-uses feature 007's `ChatBody`/`ChatReply` shapes (import from `backend.app.agent_service.schemas` — no duplication). Internally calls `route_text(...)` and projects the result to the chat envelope.
- `backend/app/agent_router/search_adapter.py` → `router = APIRouter()`, `GET /api/search`. Internally forces intent to `search_products` and returns `{products: [...]}` (matching the existing `productContext` expectation).
- `backend/app/main.py`:
  - REMOVE the line `from backend.app.agent_service import chat_router` and the `app.include_router(chat_router, tags=["chat"])` call. **(Single-line rollback target.)**
  - ADD imports for `backend.app.agent_router.api`, `chat_adapter`, `search_adapter`, and `backend.app.products_stub`.
  - ADD `app.include_router(...)` calls for each new router (4 lines).
  - ADD a startup hook (FastAPI `lifespan` or `@app.on_event("startup")`) that calls `get_sbert_model()` + `get_intent_index()` to warm caches.
- **Verify (M5):**
  - `uvicorn backend.app.main:app --reload` boots, prints "SBERT warm" within ~3 s on a warm machine.
  - `pytest backend/tests/test_agent_route_endpoint.py` covers the verbose envelope + 401-when-missing-bearer.
  - `pytest backend/tests/test_chat_router.py` (existing) still passes after the internal swap — the chat envelope is unchanged.
  - `pytest backend/tests/test_search_route.py` covers `GET /api/search?q=`.

### M6 — Frontend wire-up (small, additive)

- `frontend/src/services/searchService.js`: no change to the function signature — the URL `/api/search?q=...` is now real. *(Removes the mock fallback when `VITE_USE_MOCKS=false`.)*
- `frontend/src/services/agentService.js` (new, ~15 lines): `routeText(text)` POSTs `/api/agent/route`. *(Exported but unused in v1 — wired in for the demo-finale "raw intent" debug panel if requested; otherwise dead-but-tested.)*
- No change to `chatbotContext.jsx`, `ChatWindow.jsx`, `ChatInput.jsx`. The chat endpoint shape is unchanged (FR-7).
- **Verify (M6):**
  - `npm test` green.
  - Manual: search bar with `VITE_USE_MOCKS=false`, query `"laptop"` returns the seeded laptop row.

### M7 — Docs, env, build glue (P3 / P6)

- `.env.example` — append:
  ```
  # Feature 008 — SBERT intent router
  MODELS_DIR=./models/sbert
  ALLOW_MODEL_DOWNLOAD=0
  INTENT_CONFIDENCE_THRESHOLD=0.45
  CATEGORY_MATCH_THRESHOLD=0.55
  ```
- `pyproject.toml` — append `sentence-transformers>=3.0,<4`, `numpy>=1.26`.
- `Makefile` — add `sbert-download` (one-shot pull into `./models/sbert/`) and `agent-test` (`pytest backend/tests/test_agent_router.py backend/tests/test_intent_classifier.py backend/tests/test_entities.py -v`).
- `README.md` — append a "Run (SBERT intent router — feature 008)" section: download the model once, start the backend, query.
- `docs/architecture.md` — append "Feature 008 — SBERT Intent Router" section listing decisions D30..D40 (see spec §2).

### M8 — Cleanup / audit close

- Append the implementation session entry to `specs/008-sbert-intent-router/conversation-history.md` (P7).
- Run `ruff check backend/app/agent_router backend/app/products_stub backend/tests/test_*sbert* backend/tests/test_*intent* backend/tests/test_*entities* backend/tests/test_*agent_router* backend/tests/test_*search* backend/tests/test_*products_stub*` — fix any findings.
- Run `make test` end-to-end; confirm green.
- Verify `git diff --stat backend/agent/ local-marketplace2/` is empty (FR-14).

## 3. Files touched (summary, for review)

| New | Touched (append-only) | Re-wired (one-line revert) | Not touched (audit assertion) |
| :-- | :-- | :-- | :-- |
| `backend/app/agent_router/{__init__, sbert, intents, entities, route, projection, api, chat_adapter, search_adapter}.py` | `backend/app/main.py`, `backend/app/core/config.py`, `.env.example`, `pyproject.toml`, `Makefile`, `README.md`, `docs/architecture.md` | `/api/chat` route binding in `main.py` only | All of `backend/agent/`, all of `local-marketplace2/`, `backend/app/agent_service/` (kept dormant) |
| `backend/app/products_stub/{__init__, schemas, store, parser, router}.py` | | | |
| `backend/tests/test_{sbert_loader, intent_classifier, entities, agent_router, agent_route_endpoint, search_route, products_stub}.py` | `backend/tests/test_chat_router.py` (assertions only, no setup change) | | |

## 4. Risks & mitigations

| Risk | Mitigation |
| :-- | :-- |
| First-time SBERT download fails behind a corporate firewall (carried over from feature 002 ASR) | `MODELS_DIR` + `ALLOW_MODEL_DOWNLOAD=0` defaults force the operator to pre-download; failure is loud + actionable at startup, not silently at request time. `make sbert-download` documented. |
| Cold model load slows CI / dev reload | Cache is lazy; tests stub `get_sbert_model()` via the same `reset_*_cache()` hook feature 007 uses. CI never loads the real model. |
| Intent prototypes drift from real user phrasing | Threshold (`INTENT_CONFIDENCE_THRESHOLD`) is env-controlled. Add a "low-confidence" intent telemetry line (`logger.info`) to capture utterances for later prototype tuning. |
| The 006 stub diverges from the eventual real 006 | Stub mirrors the read contract from `local-marketplace2/.../routes/products.py` exactly; only the *extra* query params (Q7) are forward-compatible additions, clearly tagged `# STUB-006`. On 006 merge, the stub package is deleted (1 PR) and `main.py` includes the real router instead. |
| Frontend breaks because the chat envelope changed | FR-7 freezes the chat envelope; `test_chat_router.py` is the contract guard. |

## 5. Sequencing & approval gate

1. ⬜ **User approval of this `plan.md`** ← Constitution P1, current step.
2. ⬜ M1 → M7 in order (each milestone's "Verify" step is its own gate).
3. ⬜ M8 close-out.

The agent will NOT touch any implementation file before step 1 is granted.
