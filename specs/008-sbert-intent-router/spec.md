---
title: "Feature 008: SBERT Intent Router (Lightweight V1 Agent)"
feature: 008-sbert-intent-router
status: "Shipped (V1) — last updated 2026-06-23"
supersedes: "007-chatbot-integration (HTTP wiring only — feature 002 code stays in-repo, off-the-wire)"
related: ["002-agent", "004-frontend", "005-catalog", "006-vendor-product-management (merged in-tree)"]
---

# Feature 008: SBERT Intent Router

> **How to read this document**
>
> This spec is split into two parts:
>
> 1. **Part A — Reader Start Here.** A short, plain-English summary of what
>    actually shipped, the end-to-end flow, the live HTTP surface, and a
>    chronological table of every post-launch fix. Read this first.
> 2. **Part B — Historical contract.** The original architectural contract
>    that drove implementation (sections 1–8) plus the 2026-06-23 cutover
>    addendum (section 9). Kept verbatim per **Constitution P3 (audit trail)**
>    and **P6 (file idempotency / append-only)**. Read this when you need to
>    know *why* a decision was made, not just *what* the system does today.
>
> The two parts agree. Where the contract said "stub", the addendum (§9) and
> Part A both reflect that the real 006 service is now live.

---

# Part A — Start from here :

## A.1 One-paragraph summary

Feature 008 is a **lightweight, single-pass natural-language agent** for the
Local Marketplace. A user types or speaks an utterance ("Show me iPhone 15
under ₹60,000", "Add a new Samsung S24 for ₹45,000") and the backend turns
it into exactly one call against the existing Marketplace REST API. There is
**no LLM on the request path** — only **SBERT** (`all-MiniLM-L6-v2`, ~80 MB,
CPU) for intent classification, plus deterministic regex/token rules for
entity extraction. No planner, no orchestrator, no session memory in V1 version. will implement in V2 version going forward. 

## A.2 Why this exists

The original Feature 002 agent (planner + orchestrator + tool registry +
LLM gateway) is too heavy to ship for V1. Feature 008 is the smallest thing
that still delivers the demo outcome: *"natural language → real product
list / real product row"*. The Feature 002 code is kept on disk
(Constitution P6) but no HTTP route imports it, so a one-line revert in
`backend/app/main.py` would bring it back.

## A.3 What the user can do (V1 scope) : 

| Role     | Channel              | Examples                                                            |
| :------- | :------------------- | :------------------------------------------------------------------ |
| Customer | Search bar, Chatbot  | "show me laptops under 50k", "find Samsung phones"                  |
| Customer | Chatbot (voice→text) | Same as above, dictated via browser Web Speech API                  |
| Vendor   | Chatbot, Add-Product modal | "add Amul milk 1L for ₹29", "update product 42 to ₹50,000", "delete the milk", "show my listings" |
| Anyone   | Chatbot              | "what categories do you have?"                                      |

Out of scope for V1: image input/OCR, multilingual queries, multi-turn
slot-filling, vector product search, geolocation ("near me").

## A.4 The seven intents : 

| Intent             | Allowed roles    | Backend call (final)                                         |
| :----------------- | :--------------- | :----------------------------------------------------------- |
| `search_products`  | customer, vendor | `GET /api/products?...` (in-process via `product_service`)   |
| `add_product`      | vendor           | `POST /api/products/from-description`                        |
| `update_product`   | vendor           | `PUT /api/products/{id}`                                     |
| `delete_product`   | vendor           | `POST /api/products/delete-by-description` (or by id)        |
| `get_my_listings`  | vendor           | `GET /api/products?vendor_id=<me>`                           |
| `get_categories`   | customer, vendor | `GET /api/catalog/categories`                                |
| `unknown`          | any              | *no call* — polite "I can help you search / add / …" reply   |

## A.5 End-to-end flow : 

```
User
  │   types or dictates an utterance
  ▼
Frontend (React)                              ┌─ ChatInput.jsx / ProductExtractPanel.jsx
  │   - text or voice→text (Web Speech API)   │  - single-shot submit guards (useRef)
  │   - optional `intent` hint                │    prevent React 18 StrictMode double-fire
  ▼                                           └─ services/chatbotService.js → /api/chat
Backend (FastAPI)
  │   /api/chat  or  /api/agent/route  or  /api/search?q=...
  ▼
agent_router/chat_adapter.py            ← validates JWT, extracts (role, vendor_id)
  │   - accepts optional `intent` hint  ← used by Add-Product modal to force `add_product`
  ▼
agent_router/route.py :: route_text(text, role, vendor_id, forced_intent=None)
  │   1. classify(text)  → SBERT cosine vs. INTENT_PROTOTYPES
  │      + imperative-verb tiebreaker for low-confidence terse commands
  │   2. role gate (FR-4)
  │   3. entity extraction (regex price/id/keywords, SBERT category)
  │   4. dispatch via match/case
  ▼
services/product_service.py             ← real 006 service (SQLAlchemy / SQLite locally)
  │
  ▼
agent_router/projection.py              ← shape rows into the {id,name,price,vendor,...}
                                          envelope the frontend expects
  │
  ▼
JSON response   {reply, listings, sessionId}  or  {intent, entities, reply, listings, ...}
```

Latency budget: SBERT model + intent embeddings warmed once at app startup
(lifespan hook), targeting <100 ms p95 per turn on a developer Mac.

## A.6 Live HTTP surface

| Verb / Path                          | File (owner)                                       | Notes |
| :----------------------------------- | :------------------------------------------------- | :---- |
| `POST /api/chat`                     | `backend/app/agent_router/chat_adapter.py`         | Chatbot wire shape. Accepts optional `intent` hint. |
| `POST /api/agent/route`              | `backend/app/agent_router/api.py`                  | One-shot verbose envelope (intent, entities, api_called, …). |
| `GET  /api/search?q=...`             | `backend/app/agent_router/search_adapter.py`       | Forces intent = `search_products`. |
| `GET/POST/PUT/DELETE /api/products`  | `backend/app/api/routes/products.py` (Feature 006) | Real service, SQLite locally. |
| `GET  /api/catalog/categories`       | `backend/app/api/routes/catalog.py`  (Feature 006) | Real, seeded taxonomy. |
| `GET  /api/orders`, `POST /api/orders` | `backend/app/api/routes/orders.py`               | V1 stub — GET returns `[]`, POST returns 501. Added to silence frontend 404s. |

## A.7 What shipped — module map

```
backend/app/
├── agent_router/                  ← NEW (Feature 008)
│   ├── sbert.py                   ─ lru_cache singleton for the model
│   ├── intents.py                 ─ INTENT_PROTOTYPES + classify() + verb tiebreaker
│   ├── entities.py                ─ price / product_id / keywords / category extractors
│   ├── route.py                   ─ route_text(text, role, vendor_id, forced_intent)
│   ├── projection.py              ─ row → Listing shape (frontend stable)
│   ├── chat_adapter.py            ─ POST /api/chat
│   ├── search_adapter.py          ─ GET  /api/search
│   └── api.py                     ─ POST /api/agent/route
├── api/routes/orders.py           ← NEW V1 stub
├── models/{category,product,subcategory}.py  ← AUTHORED HERE to fill 006 ORM gap
├── catalog/parser.py              ← TOUCHED (bare numbers, comma prices, stock default = 1)
└── db/session.py                  ← TOUCHED (project-root-absolute SQLite path)
```

```
frontend/src/
├── components/chatbot/ChatInput.jsx              ← single-shot submit guard, voice auto-submit
├── components/chatbot/MessageBubble.{jsx,css}    ← debug badge for SBERT intent/confidence
├── components/products/ProductExtractPanel.jsx   ← voice auto-submit, "Create from description" via /api/chat
├── pages/VendorPage.jsx                          ← createFromDescription routes via /api/chat with intent="add_product"
├── pages/SearchPage.jsx                          ← reads `products` OR `results` from backend
├── services/chatbotService.js                    ← sendChat(message, sessionId, image, intent)
└── store/{chatbotContext,productContext}.jsx     ← surface backend debug, support new response shape
```


## A.9 How to run (V1, local dev)

```bash
# one-time
make sbert-download                    # pulls all-MiniLM-L6-v2 into ./models/sbert/
cp .env.example .env                   # MODELS_DIR, ALLOW_MODEL_DOWNLOAD, thresholds
make install                           # backend (uv/pip) + frontend (npm) deps

# run
make run                               # spawns uvicorn (backend) + vite (frontend)
# or, separately:
#   uvicorn backend.app.main:app --reload --port 8000
#   (cd frontend && npm run dev)
```

Smoke test:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Authorization: Bearer <vendor-jwt>' \
  -H 'Content-Type: application/json' \
  -d '{"message":"add Amul milk 1L for 29","sessionId":null}'
# → { reply: "Added: Amul Milk (₹29)", listings: [ ... ], sessionId: "..." }
```

## A.10 Glossary

- **SBERT** — Sentence-BERT. Here, `sentence-transformers/all-MiniLM-L6-v2`, an 80 MB English sentence-embedding model.
- **Intent prototypes** — A small fixed corpus of paraphrases per intent. The user's utterance is embedded and cosine-matched against them. The highest score above `INTENT_CONFIDENCE_THRESHOLD` (default `0.45`) wins; otherwise `unknown`.
- **Imperative-verb tiebreaker** — A deterministic rule layered on top of SBERT: if the utterance starts with a known imperative verb (add / update / delete / show / find / list) and the SBERT score is below a margin, the verb's intent wins. Fixes terse "Add iPhone 50000" → `add_product`.
- **`forced_intent`** — Optional caller-supplied intent hint that bypasses classification. Validated server-side against an allow-list. Used by the Add-Product modal so a voice description is *always* an add, never a delete/update.
- **006 cutover** — The day the real `006-vendor-product-management` service replaced this feature's in-memory products stub. See §9.
- **Constitution P6 (append-only)** — Why this document keeps the original sections below verbatim instead of rewriting them.

---

# Part B — Historical contract

# Feature 008: SBERT Intent Router — Specification

> Architectural contract for feature `008-sbert-intent-router` (Constitution P3).
> Mark every unknown `[NEEDS CLARIFICATION: ...]` — never guess (Constitution P2).
> Outranked by `specs/constitution.md` and the master `SPEC.md`.
> **Authority boundary:** the product/catalog *schema* and the product *REST contract*
> are owned by `local-marketplace/specs/006-vendor-product-management`

## Feature Overview

**Problem statement.** Feature 002 ships a planner / orchestrator / tool-registry / session-store
agent that is good for the long-term roadmap but expensive to ship for v1: it requires an LLM
gateway (Circuit/OpenAI) at runtime, multi-turn confirmation gating, and operator-grade
infra (Redis sessions, prompts, retries). For the v1 demo we want **intelligent query
understanding** without any of that: a single forward pass from "natural language" to
"existing marketplace API call", with a hard "no LLM in the request path" constraint.

**Why this feature exists.** It is the smallest possible *lightweight* agent that delivers
the user-visible outcome ("Show me iPhone 15 under ₹60,000" → real product list; "Add a
new Samsung S24 for ₹45,000" → real product row) by reusing the existing marketplace REST
surface. SBERT (sentence-transformers, MiniLM-L6-v2, ~80 MB, CPU) does **intent
classification** against a fixed set of intent prototypes; deterministic regex / token rules
do **entity extraction**; the result is a one-shot routed HTTP call against the existing
products API. No planner, no orchestrator, no tool registry, no session memory.

**Replaces (on the wire):** Feature 007's `/api/chat` wiring. The feature-002 agent code
stays in-tree for the long-term roadmap and is *not* deleted (P6: idempotent); it is simply
no longer reached by any HTTP route after this feature lands. A single-line revert in
`backend/app/main.py` restores it.

**v1 input modalities:** text (keyboard) and voice → text (browser-side ASR via Web Speech API
on the chat surface; the search bar is keyboard-only by design). The router only ever sees
text on the wire. Image input remains on hold (carried forward from feature 007 FR-6).

**Scope — Included**

- A new module `backend/app/agent_router/` (importable as `backend.app.agent_router`)
  with: SBERT loader + intent classifier, deterministic entity extractors, and a router
  that maps an `(intent, entities, role)` triple to exactly one downstream products-API call.
- A *new* `POST /api/agent/route` endpoint (single-turn, stateless, JSON-only) that the
  search bar **and** chatbot both call.
- Re-wire `POST /api/chat` (currently feature 007's proxy to feature 002) to call the
  same router under the hood, preserving the existing `{message, sessionId}` request
  body and `{reply, listings, sessionId}` response body so the chatbot UI is unchanged.
- Re-wire `GET /api/search?q=…` (currently mocked in the frontend; not yet implemented
  server-side) to call the router with intent forced to `search_products`.
- A **local stub** of the feature-006 products API at `backend/app/products_stub/`
  exposing the same REST contract (`GET /api/products`, `POST /api/products`,
  `PUT /api/products/{id}`, `DELETE /api/products/{id}`, plus richer query params per Q7):
  in-memory store, seeded with 8–12 example products spanning the seeded categories,
  scoped by the JWT-derived vendor for writes. Drop-in for feature 006's eventual merge.
- Frontend wiring: flip `searchService.searchProducts` to call `/api/agent/route` (one-shot)
  and confirm the chatbot still talks to `/api/chat` (now SBERT-backed).
- Tests at `backend/tests/test_agent_router.py` (intent classifier accuracy on a fixed
  prompt suite + entity extractor + router → stub round-trip).
- Wire-level tests at `backend/tests/test_search_route.py` and an update to
  `backend/tests/test_chat_router.py` reflecting the rewired internals (assistant text is
  still returned; planner is no longer invoked).
- Docs: this `spec.md`, `plan.md`, `prompts.md`, `conversation-history.md`; updates to
  `docs/architecture.md`, `README.md`, `.env.example`, `pyproject.toml`, `Makefile`.

**Scope — Excluded**

- Multi-turn conversation, confirmation gating, session memory, slot-filling repair loops.
  (One turn = one classification + one HTTP call + one response.)
- Any LLM call (OpenAI, Circuit, Anthropic, etc.) on the request path. SBERT is the **only**
  ML model loaded.
- Image input / OCR (deferred — feature 007 FR-6 carries over).
- Re-implementing the feature-006 products *schema* (no migrations, no Alembic, no Postgres
  in this feature). The stub is in-memory; persistence is feature 006's responsibility.
- Embedding **products** for semantic product search. Intent prototypes are embedded; product
  matching is rule-based (q-substring + price filter + category match). Vector product search
  is explicitly future work.
- Editing, deleting, or behaviour-changing anything in `backend/agent/` (feature 002 code).
  P6 keeps it untouched.
- Editing anything under `local-marketplace2/` (the other engineer's tree is read-only per
  the user prompt).

## 1. User Scenarios & Edge Cases

1. **Customer — natural-language search via the search bar.**
   - *Given* an authenticated customer on the Search page,
   - *When* they type `"Show me iPhone 15 under ₹60,000"` and submit,
   - *Then* the router classifies intent = `search_products`, extracts
     `entities = {keywords: "iphone 15", max_price: 60000}`, calls
     `GET /api/products?q=iphone+15&max_price=60000`, and returns the result list.
   - **Edge cases:**
     - Empty `q` after extraction → return top-N most-recent products (do not 400).
     - Price written as `"60k"`, `"60,000"`, `"60000"`, `"sixty thousand"` → first three
       MUST parse; the spelled-out form MAY be deferred (recorded as `[NEEDS CLARIFICATION]`
       if any reviewer cares).
     - "near me" → ignored in v1 (no geolocation pipeline yet); flagged in the response's
       `meta.ignored` array.

2. **Customer — natural-language search via the chatbot.**
   - Same as above but POSTed to `/api/chat` with a `sessionId`. The router returns a
     chatty `reply` ("I found 3 matches") in addition to `listings`.
   - **Edge case:** no matches → `reply = "I couldn't find anything matching that — try a
     different brand or higher budget."`, `listings = []`. Never 404.

3. **Vendor — add product from voice.**
   - *Given* an authenticated vendor on the chatbot,
   - *When* they speak `"Add a new Samsung S24 for ₹45,000"`,
   - *Then* the browser transcribes to text, POSTs `/api/chat`, intent =
     `add_product`, entities = `{name: "Samsung S24", price: 45000}`,
     router calls `POST /api/products/from-description` (stubbed) with the *raw*
     transcript as `description_text` (006 FR-4 owns the parsing), returns
     `reply = "Added: Samsung S24 (₹45,000)"`, `listings = [<the new row>]`.
   - **Edge cases:**
     - No parseable price → 006 returns 400; router returns
       `reply = "I couldn't pick up a price — please include one (e.g. ₹45,000)."`,
       `listings = []`. HTTP 200 to the frontend (no red toast).
     - Role = customer → 403 from the stub; router converts to
       `reply = "Only vendors can add products."`, listings empty.

4. **Vendor — update by ID.**
   - `"Update the price of product 12345 to ₹50,000"` → intent = `update_product`,
     entities = `{product_id: "12345", price: 50000}`, calls
     `PUT /api/products/12345` with `{price: 50000}`. Reply confirms.
   - **Edge case:** "update my iPhone listing" with no explicit ID → router does a
     **single** `GET /api/products?vendor_id=<me>&q=iphone`, picks the highest-scoring
     match (if exactly one), then PUTs. Tie or zero → reply = "I found N candidates —
     please give me the product ID." No write.

5. **Vendor — delete by description.**
   - `"Delete the milk"` → intent = `delete_product`, entities = `{description: "milk"}`,
     calls `POST /api/products/delete-by-description` with `{description_text: "milk"}`.
     006 FR-9 owns the matching; router just relays the response.

6. **Vendor — list my listings.**
   - `"Show my listings"` / `"What products do I have?"` → intent = `get_my_listings`,
     calls `GET /api/products?vendor_id=<me>`. Reply paraphrases the count.

7. **Anyone — list categories.**
   - `"What categories do you have?"` → intent = `get_categories`, calls
     `GET /api/catalog/categories` (stubbed). Reply formats the list.

8. **Unknown / out-of-scope query.**
   - `"What's the weather?"` → top intent confidence < threshold → router replies
     `"I can help you search, add, update, or delete products. What would you like to do?"`
     and makes **no** HTTP call.

## 2. Functional Requirements & Decisions

| ID | Requirement (MUST/SHOULD) | Decision taken & rationale |
| :-- | :-- | :-- |
| FR-1 | The router MUST classify every inbound utterance into exactly one of: `search_products`, `add_product`, `update_product`, `delete_product`, `get_my_listings`, `get_categories`, `unknown` (7 labels). | Q3 = "broader CRUD"; `unknown` is a hard fallback so we never call an API on garbage input. |
| FR-2 | Classification MUST use SBERT (`sentence-transformers/all-MiniLM-L6-v2`) with cosine similarity against a fixed set of seeded *intent prototypes* (≥3 paraphrases per intent, English). The highest-scoring intent above `INTENT_CONFIDENCE_THRESHOLD` (default `0.45`) wins; below threshold → `unknown`. | Q5; matches "SBERT-based semantic intent matching" from the user prompt. Threshold is configurable via env so we can tune from the test suite without code edits. |
| FR-3 | Entity extraction MUST be deterministic and LLM-free. Required extractors: `price` (₹/Rs/INR/k/comma forms), `product_id` (UUID-or-int token after the words "id"/"#"/"product"), `keywords` (the residue after stop-words + intent keywords are stripped), `category` (SBERT-matched against the seeded category names with its own threshold `CATEGORY_MATCH_THRESHOLD = 0.55`). | Q4 = "regex + SBERT for category"; no LLM. |
| FR-4 | The router MUST enforce **role-based intent gating before** any HTTP call: customers MAY use `search_products`, `get_categories`; vendors MAY use **all** intents. Mis-matched role → reply with a polite refusal, no HTTP call, HTTP 200 to the frontend. | Mirrors feature 002's tool registry RBAC; surfaces same UX without the planner. |
| FR-5 | The router MUST be **stateless** — no session store, no Redis, no in-process turn history. Each call is independent. | Replaces feature 007's session pre-seeding. Drops Redis as a dependency for the router (feature 002 code is no longer reached so the dep is also unreached). |
| FR-6 | `POST /api/agent/route` MUST accept `{text: str, role?: "customer"\|"vendor"}` (role optional — defaults from JWT) and return `{intent, entities, reply, listings, api_called, api_status, meta}`. JSON-only; multipart is rejected with 415. | New endpoint per Q8 = "reuse_chat" plus a clean single-turn surface; the chatbot does not need this verbose envelope, but the search bar does. |
| FR-7 | `POST /api/chat` MUST be rewired to call the router but **preserve the existing request and response wire shapes** from feature 007 (`{message, sessionId}` → `{reply, listings, sessionId}`). `sessionId` becomes a UUID echo (no server-side state). | Keeps the chatbot UI unmodified (P6 for the frontend). |
| FR-8 | `GET /api/search?q=<text>` MUST be added server-side, calling the router with intent forced to `search_products` (skip classification — `q` is already a search query by convention). Response shape MUST match the frontend's current `searchService` expectation (`{products: [...]}` or `{listings: [...]}` — see FR-10). | The current frontend search bar already calls this endpoint (mocked). Server-side implementation closes the mock. |
| FR-9 | A **local stub** of the feature-006 products API MUST be added under `backend/app/products_stub/`, exposing the *same routes and bodies* as `local-marketplace2/.../routes/products.py` and `routes/catalog.py`, **plus** these extra query params on `GET /api/products`: `?q=`, `?max_price=`, `?min_price=`, `?category=`, `?vendor_id=`. The stub is in-memory (dict), seeded at startup, vendor-scoped for writes via the same JWT path as feature 003. Tagged in code with `# STUB-006: replace with feature 006 when merged`. | Q2 = "stub"; Q7 = "richer stub". Forward-compatible extras are flagged so the 006 engineer can either adopt them or we adapt the router when they merge. |
| FR-10 | Response shape returned to the frontend for product lists MUST match feature 007's `Listing` shape (`id, name, price, vendor, rating, availability`) so the existing `ProductCard` renders unchanged. The 006 raw catalog fields are projected to this shape inside `backend/app/agent_router/projection.py`. | Frontend stability (P6). |
| FR-11 | The SBERT model MUST be loaded **once at FastAPI startup** (lifespan / lru_cache, same pattern as feature 007's orchestrator), and intent-prototype embeddings MUST be pre-computed at the same time. Per-request latency budget: < 100 ms p95 on a developer Mac (no GPU). | Q5 deployment shape D2 ("pre-compute at startup"). |
| FR-12 | The model files MUST resolve from a `MODELS_DIR` env var (default `./models/sbert/`). If absent, the loader MUST attempt a single offline download via `sentence-transformers` *only when* `ALLOW_MODEL_DOWNLOAD=1` is set; otherwise it MUST fail fast at startup with a clear "set MODELS_DIR or ALLOW_MODEL_DOWNLOAD=1" message. | Mirrors feature 002 ASR's offline-first pattern; keeps CI deterministic. |
| FR-13 | New routers MUST be wired into `backend/app/main.py` under `/api/agent`, `/api/products` (stub), `/api/catalog` (stub). The existing `/api/chat` import line is updated to point at the new chat adapter; no other existing route changes. | Constitution P6. |
| FR-14 | The feature-002 modules (`backend/agent/orchestrator.py`, `planner.py`, `tools/`, `prompts/`, `memory.py`, `llm/`) MUST NOT be edited or deleted by this feature. After the feature lands, no HTTP route imports them. | P6 / supersedes-on-the-wire-only commitment. |

## 3. Success / Acceptance Criteria

- [ ] `POST /api/agent/route` with `{text: "Show me iPhone 15 under ₹60,000"}` (customer JWT) returns `intent="search_products"`, `entities.keywords ∋ "iphone"`, `entities.max_price=60000.0`, `api_called="GET /api/products"`, `listings` non-empty for the seeded catalog.
- [ ] `POST /api/agent/route` with `{text: "Add a new Samsung S24 for ₹45,000"}` (vendor JWT) returns `intent="add_product"`, `api_called="POST /api/products/from-description"`, `api_status=201`, `listings` containing the new row.
- [ ] `POST /api/agent/route` with `{text: "Update product 42 to ₹50,000"}` (vendor JWT) returns `intent="update_product"`, calls `PUT /api/products/42`, returns the updated row.
- [ ] `POST /api/agent/route` with `{text: "Delete the milk"}` (vendor JWT) returns `intent="delete_product"`, calls `POST /api/products/delete-by-description`.
- [ ] `POST /api/agent/route` with `{text: "What categories do you have?"}` returns `intent="get_categories"`, calls `GET /api/catalog/categories`.
- [ ] `POST /api/agent/route` with `{text: "weather tomorrow?"}` returns `intent="unknown"`, `api_called=null`, no HTTP call made, polite reply.
- [ ] Customer attempting `add_product` → polite refusal, no HTTP call, HTTP 200.
- [ ] `POST /api/chat` continues to satisfy feature 007's existing test contract (replied text + listings + sessionId echo).
- [ ] `GET /api/search?q=…` returns products from the stub.
- [ ] Intent classifier achieves ≥ 90% accuracy on the test suite of ≥ 30 paraphrased utterances spanning the 6 supported intents + 5 `unknown` distractors.
- [ ] Per-turn p95 latency < 100 ms on the developer machine (excluding cold model load).
- [ ] `make test` green; `ruff check` clean; no edits under `backend/agent/`.
- [ ] `.env.example` updated (`MODELS_DIR`, `ALLOW_MODEL_DOWNLOAD`, `INTENT_CONFIDENCE_THRESHOLD`).
- [ ] `docs/architecture.md` appended with the decisions D30–D40 (this feature).

## 4. API & Module Surface

| Surface | Verb / Path | Owner | Notes |
| :-- | :-- | :-- | :-- |
| Agent router (1-shot) | `POST /api/agent/route` | `backend/app/agent_router/api.py` | New. Verbose envelope per FR-6. |
| Chatbot adapter | `POST /api/chat` | `backend/app/agent_router/chat_adapter.py` | Re-wired. Feature 007's wire shape preserved. |
| Search adapter | `GET /api/search?q=` | `backend/app/agent_router/search_adapter.py` | New. Maps to `search_products` directly. |
| Products stub | `GET/POST/PUT/DELETE /api/products[...]` | `backend/app/products_stub/router.py` | New. Mirrors 006 contract + 5 query params. |
| Catalog stub | `GET /api/catalog/categories`, `/subcategories` | `backend/app/products_stub/router.py` | New. Seeded taxonomy. |
| SBERT loader | n/a | `backend/app/agent_router/sbert.py` | `lru_cache`-singleton; lifespan-warmed. |
| Intent classifier | n/a | `backend/app/agent_router/intents.py` | Prototypes + cosine. |
| Entity extractors | n/a | `backend/app/agent_router/entities.py` | Regex + token rules. |
| API router | n/a | `backend/app/agent_router/route.py` | `(intent, entities, role)` → HTTP call. |

## 5. Requirement Completeness / Definition of Done

- [ ] No unresolved `[NEEDS CLARIFICATION]` (P2). *(Two recorded, both deferred — see §6.)*
- [ ] `plan.md` written and **user-approved** before any implementation (P1).
- [ ] All FRs (§2) covered by passing tests where testable.
- [ ] All Acceptance Criteria (§3) met and verified.
- [ ] `make test` green and `ruff check` clean.
- [ ] Audit trail committed: `spec.md`, `plan.md`, `prompts.md`, `conversation-history.md`.
- [ ] `docs/architecture.md` updated with decisions this feature introduced.
- [ ] No file under `backend/agent/` or `local-marketplace2/` modified (verified by `git diff --stat`).

## 6. Deferred / Clarifications

- `[NEEDS CLARIFICATION: spelled-out numbers like "sixty thousand"]` — v1 ships digit-form only. If the demo audience uses spelled-out numerals, raise a follow-up issue.
- `[NEEDS CLARIFICATION: multilingual queries]` — Q5 chose English-only MiniLM. Multilingual SBERT (`paraphrase-multilingual-MiniLM-L12-v2`) is a 5-line swap if needed.
- The temporary frontend auth shim from feature 007 Session 3 (`authContext.jsx`, `authService.js`) is **out of scope here** — slated for a future `009-frontend-auth-bridge` feature.

## 7. Test Plan

| Test | File | Asserts |
| :-- | :-- | :-- |
| Intent classifier accuracy ≥ 0.9 on 30-utterance suite | `backend/tests/test_intent_classifier.py` | FR-2 |
| Entity extractor — price forms, IDs, keywords, category | `backend/tests/test_entities.py` | FR-3 |
| Router → stub round-trip for each of the 6 intents | `backend/tests/test_agent_router.py` | FR-1, 4, 9, 10 |
| `POST /api/agent/route` contract (verbose envelope) | `backend/tests/test_agent_route_endpoint.py` | FR-6 |
| `POST /api/chat` regression — feature 007 contract still holds | `backend/tests/test_chat_router.py` (updated) | FR-7 |
| `GET /api/search?q=` contract | `backend/tests/test_search_route.py` | FR-8 |
| Stub products API contract matches 006 | `backend/tests/test_products_stub.py` | FR-9 |
| Role gating — customer attempting `add_product` | `backend/tests/test_agent_router.py::test_role_gating` | FR-4 |
| `unknown` intent → no HTTP call | `backend/tests/test_agent_router.py::test_unknown_does_not_call_api` | FR-1, FR-14 |
| Lifespan / model load — no network at request time | `backend/tests/test_sbert_loader.py` | FR-11, FR-12 |

## 8. Out-of-Repo Reference (read-only)

| Path | Purpose for this feature |
| :-- | :-- |
| `local-marketplace2/local-marketplace/specs/006-vendor-product-management/spec.md` | Authoritative product/catalog REST contract this feature stubs. |
| `local-marketplace2/.../backend/app/api/routes/products.py` | Reference implementation (route shapes & validation) we mirror in `products_stub`. |
| `local-marketplace2/.../backend/app/schemas/product.py` | Reference for `ProductRead`, `ProductCreate`, `ProductUpdate`, `ProductDescriptionRequest`. |
| `local-marketplace2/.../backend/app/catalog/enums.py` | `UnitType` enum copied verbatim (small enum, OK to duplicate; will collapse on 006 merge). |

---

## 9. Addendum — V1 cleanup, real-006 cutover (2026-06-23)

The 006 PR merged on top of this feature's working tree. As of this addendum,
the architecture pieces below are the **active** state (superseding the
stub-flavoured wording earlier in this spec). Earlier sections are kept
verbatim per Constitution P7 (specs are append-only).

| Item | Was | Is |
|---|---|---|
| Products data path (FR-9) | `backend/app/products_stub/` (in-memory dict, seeded) | `backend/app/services/product_service.py` (feature 006, SQLAlchemy `Session`) |
| Catalog data path | `products_stub/` (in-memory) | `backend/app/api/routes/catalog.py` + seeded taxonomy in `backend/app/catalog/seed_data.py` |
| `main.py` mounts (FR-13) | `/api/products` + `/api/catalog` from the stub | `/api/products` + `/api/catalog` from real 006 routers |
| Router dispatch | `route.py` ↔ `products_stub.store` | `route.py` ↔ `services.product_service` via `_db_session()` (sync `SessionLocal`) |
| Listing projection | maps stub `Product` dataclass | maps 006 `ProductRead` pydantic |
| Stub-coupled tests | `test_products_stub.py`, stub seed data in `test_agent_router.py` | `test_products_stub.py` removed. `test_agent_router.py` rewritten to use the existing `catalog_db` fixture (SQLite, seeded) and a `patched_session` fixture that redirects `route._db_session` to the test session. |

FR-1..FR-8, FR-10..FR-15 are unchanged. Only the FR-9 stub backing is
replaced by the real 006 service. The HTTP wire shapes the frontend
consumes (`/api/chat`, `/api/agent/route`, `/api/search`) are identical.

Additional notes from the cutover:
- `backend/app/agent_service/` (early feature 007 attempt) and
  `specs/{006-backend-agent, 007-chatbot-integration}/` were deleted —
  all four were untracked and never reached `main`.
- `backend/agent/` (feature 002 planner/orchestrator) is kept on disk
  (it is committed code; user override of the earlier deletion plan).
  No HTTP route imports it.
- Three ORM model files (`backend/app/models/{category,product,subcategory}.py`)
  were authored in this cleanup to fill an upstream-006 gap (the PR
  shipped `services/product_service.py` referring to ORM models that
  were never committed). They follow 006's documented String(36)-vs-UUID
  convention (architecture log D2).
- A real upstream bug surfaced: `catalog/parser.py` does not handle
  thousands separators (`"₹45,000"` parses as 45.00). This is **not**
  fixed here (out of scope; 006's responsibility). The
  `test_vendor_add_product_happy` test exercises the path with a
  non-comma price; the comma case will start working once 006 patches
  its parser.

  ## Integration - Fixed : 

1. Issue: Local SQLite Catalog Tables Missing on Startup

make run crashed with sqlite3.OperationalError: no such table: products / categories whenever the app touched 006 catalog endpoints. The 006 ORM models existed but had no migration into the local SQLite DB.

Expected Fixed : 

The local SQLite database should be automatically initialized with all required catalog tables before any catalog-related API, service, or ORM operation is executed.
Application startup should succeed on a clean environment without requiring manual database intervention.

2. Missing 006 ORM model files : 

from backend.app.models import … failed with ModuleNotFoundError because the 006 merge brought in Alembic 0004 migration but no ORM classes. App wouldn't import.

Expected Fixed : 
Wrote backend/app/models/{category.py, subcategory.py, product.py} to match the 006 schema (string-36 UUIDs for SQLite compatibility).
Files Touch : backend/app/models/category.py, subcategory.py, product.py, __init__.py

3. SBERT misclassifying terse add/delete commands : 

"add iPhone 50000" → classified as update_product. "Add Amul milk for 29" → delete_product. SBERT prototypes were over-fit to specific brand names/numbers.

Expected Fixed : 
Rewrote INTENT_PROTOTYPES with generic placeholders; added terse-form add prototypes, added a deterministic imperative-verb tiebreaker (_VERB_HINTS/_VERB_PREFIX_RE) that pins ambiguous low-confidence utterances to the verb's intent.

Fixed Files : backend/app/agent_router/intents.py, regression tests in backend/tests/test_intent_classifier.py

4. api/orders returning 404 Error : 

Frontend polled /api/orders on multiple pages, backend had no route → 404 Eror Not Found banners coming.

Add backend/app/api/routes/orders.py 
GET /api/orders returns 200 + empty list (auth-gated)
POST /api/orders returns 501 Not Implemented with a friendly message. Wired into main.py. 

5. Chatbot voice input not auto-submitting : 
Current implementation while Speaking into the chatbot just filled the input field, user had to click "Send" manual button. 
Fixed expected : 
ChatInput.appendVoice auto-submits when the input was empty, appends-only if user was already typing. Then hardened against StrictMode. 

6. Catalog parser rejecting valid prices : 

Issue : 
Add a new Samsung S24 for 45000" (bare number) and "₹45,000" (thousands comma) were rejected; SKUs like "item-77" were sometimes parsed as a price. 
Fixed : 
Rewrote _PRICE_RES regex to accept bare numbers and comma separators, _to_price strips commas, negative look-behind avoids SKU misreads, product-name cleanup strips "add a new …" preambles and trailing prepositions.

7. Chatbot creating duplicate product rows on a single send : 

Issue : 
One voice-add in the chatbot resulted in two POSTs to /api/chat and two rows in the DB. Server log showed paired POSTs on different ports for every send.
Fixed Needed : 
Root cause was a in side-effect (queueMicrotask(() => submitWith(incoming))) inside a setText(prev => …) updater. It's intentionally double-invoking updater functions in dev → two microtasks → two POSTs. Moved the auto-submit outside the updater, added a submittingRef single-shot guard cleared on the next macrotask



