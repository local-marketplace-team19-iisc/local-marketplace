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

A conversational, deterministic marketplace agent. A customer asks (text now;
voice->text later) for an item; the agent returns in-stock listings from nearby
vendors, cheapest-first; the customer carts across vendors and books; vendors
manage stock via a dashboard. The agent's intelligence is bounded - it
semantically matches the query to catalog products, while pricing, ordering, and
stock stay deterministic.

## 3. Primary user journeys (target)

1. Customer (chatbot screen): asks for a product -> sees in-stock, in-radius
   listings cheapest-first -> adds items from one or more vendors to a cart ->
   confirms -> receives one order number (shared with each vendor for reference)
   and "Order placed - the vendor will contact you / collect in store."
2. Vendor (dashboard screen): registers with a shop location -> adds / updates /
   deletes listings (catalog product + price + stock) -> views inventory and incoming orders.

## 4. Project layout (target - each feature creates only its slice)

    ./                                    # repo root = local-marketplace
    ├── README.md  .env.example  .gitignore  Dockerfile  docker-compose.yml  Makefile  pyproject.toml
    ├── docs/
    │   ├── architecture.md               #created empty; filled incrementally as features add decisions
    │   └── api/openapi.json              # exported OpenAPI = the frontend backend contract (generated)
    ├── specs/
    │   ├── constitution.md               # Global governing rules
    │   └── NNN-slug/                     # ONE FOLDER PER FEATURE (app scaffold is not a feature)
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

The full stack the product is built toward. Rows marked `app scaffold` are the one-time runnable starting point and are not a tracked feature.

| Area | Choice | Introduced by |
| :-- | :-- | :-- |
| Backend | Python 3.11 · FastAPI + uvicorn | app scaffold  |
| Config | env `PORT` (default 8000) via `pydantic-settings` (`PORT`, `APP_VERSION`) | app scaffold  |
| Packaging | Docker (optional) | app scaffold  |
| Secrets | `.env` (gitignored); `.env.example` committed | app scaffold  |
| Quality | deps pinned (`pyproject.toml`); `ruff` lint; `pytest` + `httpx` | app scaffold  |
| Storage | PostgreSQL + PostGIS (proximity) + pgvector (semantic) | later |
| Vendor surface | Web dashboard | (later) |
| Search & semantic | Semantic retrieval; pinned model + index | (later) |
| Customer surface | Web chatbot (text; voice->text later) | (later) (UI) |
| Auth | Register / OTP login | later |
| Frontend | React 18 | later |

## 6. Non-functional requirements

- Privacy Compliance:  Customer geolocation is highly sensitive. Location data must be requested with explicit consent, processed strictly for proximity matching, and never persisted to the database.
- Security Surface: Free-text natural language inputs represent a prompt-injection and abuse vector. All inputs must be rigorously sanitized and type-validated via Pydantic before reaching the embedding pipeline or database.
- Resilience (Liveness vs. Readiness): The `app scaffold` establishes a liveness probe (is the web server process running?). Future features must introduce a separate readiness probe (is the DB reachable, are extensions loaded?) to prevent false-green states under load.
- Latency: Semantic retrieval and sorting must complete in ~ < 500ms (excluding network transit) to maintain conversational fluidity.

## 7. Acceptance criteria

The app scaffold is the one-time starting point, not a feature. Its checks do not require a `plan.md` or a `specs/` folder.

- App boots via the run command and serves on `localhost:$PORT`.
- Liveness probe: `GET /health` -> `200` with `{"status":"ok"}` and a `version` string that dynamically matches the active `APP_VERSION` environment config.
- Setting `PORT=9001` rebinds the server to 9001.
- No route other than `/health` exists.
- `pytest` passes (`backend/tests/test_health.py`); `ruff check .` is clean.
- (optional) `docker compose up` serves `/health` with `200`.

## 9. Governance & Audit

Built feature-by-feature on top of the app scaffold.

The Iron-Clad "Dry-Run" Rule: Before any implementation begins, the assigned engineer must produce a `plan.md` in the feature's directory. This plan acts as a "dry-run" summary that details exactly which files will be created, which existing files will be modified, and any architectural risks identified. Execution shall not commence until the `plan.md` is reviewed and approved.

Auditability & Versioning: Every team member must maintain a versioned history of their contributions. For each feature (`specs/NNN-slug/`), you must maintain:
    * `spec.md`: The architectural contract.
    * `prompts.md`: A chronological log of the LLM prompts provided.
    * `conversation-history.md`: The exported context of the interaction.

Authority: `docs/architecture.md` is the living decision log; updated by each feature, never pre-populated. `specs/constitution.md` outranks this document.
