---
title: Local Marketplace - Conversational AI Marketplace Agent
status: draft
---

# Local Marketplace - Conversational AI Marketplace Agent


## 1. High-level goal (Problem & Why)

Small local vendors lose customers to quick-commerce apps because they have no cheap
way to be discovered when a nearby customer wants a specific item, and customers
can't see who near them has it in stock and at what price. We connect the two
through a conversational agent.

## 2. MVP target - what we're building toward

A conversational, deterministic marketplace agent. A customer (registered with app) asks (text now; voice->text later) for an item; the agent returns in-stock listings from nearby vendors which are already onboarded (by default 5km proximity and later configurable), ranks cheapest-first products(₹ currency defined with 2 decimal points precision); then distance if tie-breaker on the price; the customer adds to cart across different vendors and places order; vendors manage inventory via a dashboard. On successful placing order, the vendor's inventory is decremented. The agent's intelligence is bounded - it semantically matches the query to catalog products(with some defined threshold), while pricing, ordering, and inventory stay deterministic.

## 3. Primary user journeys (target)

1. Customer (chatbot screen): asks for a product -> sees in-stock, in-radius listings cheapest-first -> adds items from one or more vendors to a cart ->
   confirms -> receives one unique order number (which is further having one to many relationship like one order can have many vendors) and "Order placed - with the order summary"
2. Vendor (dashboard screen): registers with a shop location -> adds / updates / deletes listings (catalog product (vendor define their own product details but   must fit the pre-defined enum category) + price + stock) -> views inventory and incoming orders.

## 4. Project layout (target - each feature creates only its slice)

    ./                                    # repo root = local-marketplace
    ├── README.md  .env.example  .gitignore  Dockerfile  docker-compose.yml  Makefile  pyproject.toml
    ├── CLAUDE.md                         # AI context file; human-owned, committed, PR-only; AI forbidden to edit
    ├── CLAUDE.local.md                   # gitignored, AI-writable; always created (not optional)
    ├── docs/
    │   ├── architecture.md               #created empty; filled incrementally as features add decisions
    │   └── api/openapi.json              # exported OpenAPI = the frontend backend contract (generated)
    ├── specs/
    │   ├── constitution.md               # Global governing rules
    │   ├── 000-app-scaffold/             # feature 000: governed but NOT a product feature; NO own spec.md (this SPEC.md is its spec); has plan.md/prompts.md/conversation-history.md
    │   └── NNN-slug/                     # ONE FOLDER PER FEATURE (product features start at 001)
    │       ├── spec.md                   # Current architectural contract for the feature
    │       ├── plan.md                   # REQUIRED: Pre-flight "Dry-Run" plan before execution
    │       ├── prompts.md                # Versioned log of LLM interactions & prompts
    │       ├── conversation-history.md   # Full context export for pedagogical audit
    │       └── contracts/                # Feature-local API schemas
    ├── backend/
    │   ├── app/
    │   │   ├── main.py                   # FastAPI(); includes routers   <- app scaffold
    │   │   ├── core/config.py            # settings                      <- app scaffold
    │   │   ├── api/routes/               # health.py (app scaffold); catalog/vendors/search/orders (later)
    │   │   ├── schemas/                  # Pydantic request/response models -> API (wire) contract (later)
    │   │   ├── models/                   # SQLAlchemy ORM = the DB tables (source of truth)       (later)
    │   │   └── db/session.py             # engine / session                                       (later)
    │   ├── migrations/                   # versioned schema history - Alembic (or Liquibase)      (later)
    │   └── tests/test_health.py          #                               <- app scaffold
    ├── db/init/01-extensions.sql         # ONE-TIME DB bootstrap (CREATE EXTENSION postgis, vector) (later)
    └── frontend/                         # React 18 (later); generates client from docs/api/openapi.json


## 5. Target stack & constraints

The full stack the product is built toward. Rows marked `app scaffold` are the one-time runnable starting point delivered by feature 000 — governed like any feature, but not a product feature.

| Area | Choice | Introduced by |
| :-- | :-- | :-- |
| Backend | Python 3.11 · FastAPI + uvicorn | app scaffold  |
| Config | env `PORT` (default 8000) via `pydantic-settings` (`PORT`) | app scaffold  |
| Packaging | Docker (optional) | app scaffold  |
| Secrets | `.env` (gitignored); `.env.example` committed | app scaffold  |
| Quality | deps pinned (`pyproject.toml`); `ruff` lint; `pytest` + `httpx` | app scaffold  |
| Storage | PostgreSQL + PostGIS (proximity) + pgvector (semantic) | later |
| Vendor surface | Web dashboard | (later) |
| Search & semantic | Semantic retrieval; pinned model + index | (later) |
| Customer surface | Web chatbot (text; voice->text later) | (later) (UI) |
| Auth | Register / email-based login (email + password or email OTP); mobile OTP not used | later |
| Frontend | React 18 | later |

## 6. Non-functional requirements

- Security Surface: Free-text(with sanitization rules provided later) natural language inputs represent a prompt-injection and abuse vector. All inputs must be rigorously sanitized and type-validated via Pydantic before reaching the embedding pipeline or database.
- Resilience (Liveness vs. Readiness): The `app scaffold` establishes a liveness probe (is the web server process running?). Future features must introduce a separate readiness probe (is the DB reachable, are extensions loaded?) to prevent false-green states under load.
- Latency: Semantic retrieval and sorting must have low latency (< 500ms) to maintain conversational fluidity.

## 7. Acceptance criteria

The app scaffold is feature 000: governed like any feature (it gets `specs/000-app-scaffold/` with `plan.md`, `prompts.md`, and `conversation-history.md`, and follows the "Dry-Run" Rule), but it is not a product feature — it delivers the runnable starting point, not a customer or vendor journey. Feature 000 has no own `spec.md`; this master SPEC.md is its spec, and the criteria below are its success criteria.

- App boots via the run command and serves on `localhost:$PORT`.
- Liveness probe: `GET /health` -> `200` with `{"status":"OK"}`
- Setting `PORT=9001` rebinds the server to 9001.
- No route other than `/health` exists.
- `pytest` passes (`backend/tests/test_health.py`); `ruff check .` is clean.
- (optional) `docker compose up` serves `/health` with `200`.

## 8. Governance & Audit

Built feature-by-feature, starting from feature 000 (the app scaffold) and continuing with product features 001+. Every feature — including 000 — is governed by the rules below.

The Iron-Clad "Dry-Run" Rule: Before any implementation begins, the assigned engineer must produce a `plan.md` in the feature's directory. This plan acts as a "dry-run" summary that details exactly which files will be created, which existing files will be modified, and any architectural risks identified. Execution shall not commence until the `plan.md` is reviewed and approved by the user itself.

Auditability & Versioning: Every team member must maintain a versioned history of their contributions. For each feature (`specs/NNN-slug/`), you must maintain the following — all committed to version control (Git), never gitignored or local-only:
    - `spec.md`: The architectural contract. (Exception: feature 000 has none — this master SPEC.md is its spec.)
    - `prompts.md`: A chronological log of the LLM prompts provided, plus a "Recurring interactions" section ranking repeated prompts by frequency and flagging any recurring ≥3 times as `[SKILL CANDIDATE]`. See constitution Principle 3.
    - `conversation-history.md`: An append-only, cumulative log of every session — context/goal, decisions and their reasoning, edge cases and unknowns discovered, and `[NEEDS CLARIFICATION]` raised/resolved — so no context is lost across sessions. See constitution Principle 3.

Authority: `docs/architecture.md` is the living decision log; updated by each feature, never pre-populated. `specs/constitution.md` outranks this document.
