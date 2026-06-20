# Conversation History — Feature 003: Vendor Customer Auth

Append-only, cumulative log of every working session on this feature
(Constitution P3 & P7). Earlier entries are NEVER overwritten or truncated.
Each entry: context/goal · decisions + reasoning · edge cases / unknowns ·
`[NEEDS CLARIFICATION]` raised or resolved · files altered.

---

## 2026-06-20 — Session 1: Feature scaffolding

- **Context / goal:** Initialise feature `003-vendor-customer-auth` via `/spec-create`.
- **Decisions:** Created `specs/003-vendor-customer-auth/` with `spec.md`, `plan.md`, `prompts.md`,
  `conversation-history.md`; set `.active_feature` → `003-vendor-customer-auth` (P7).
- **Unknowns raised:** spec.md & plan.md seeded with `[NEEDS CLARIFICATION]` markers
  to be resolved with the user before any implementation (P1, P2).
- **Files altered:** new feature folder + `.active_feature`.

## 2026-06-20 — Session 2: Phase 1 — SQLAlchemy models + Alembic migration

- **Context / goal:** User filled spec.md and plan.md (decisions: models in
  `backend/app/models/`, SQLAlchemy + Alembic, vendors unique on
  `(shop_name, shop_location)`, mock SMS, in-memory rate limiting, Docker
  Postgres+PostGIS for dev/test). Asked to implement Phase 1 only: models +
  migration, no routers/services yet.
- **Decisions:**
  - Added `backend/app/db/session.py` (engine, `SessionLocal`, `Base`) as the
    declarative base required by the models — not explicitly listed in
    plan.md's file table but a direct dependency of it (per SPEC §4 layout
    `app/db/session.py`).
  - Created `backend/app/models/{user,vendor,otp,refresh_token}.py` per
    spec.md §4 schema, plus `models/__init__.py` re-exporting all four so
    Alembic autogenerate/env.py sees full `Base.metadata`.
  - `Vendor.shop_location` uses `geoalchemy2.Geometry(POINT, srid=4326)`;
    composite `UniqueConstraint(shop_name, shop_location)` implements the
    plan's duplicate-name decision.
  - Added minimal Alembic scaffold (`alembic.ini`, `backend/migrations/env.py`,
    `script.py.mako`) since a runnable migration requires it — not itemized in
    plan.md's table but necessary to fulfill "Alembic migration file" ask.
  - `backend/migrations/versions/0001_create_auth_tables.py` creates the
    `postgis` extension, the `user_role` enum, and all 4 tables with the
    indexes/constraints from spec.md §4.
  - Appended `sqlalchemy`, `alembic`, `geoalchemy2` to `pyproject.toml`
    dependencies (idempotent append, Constitution P6).
- **Unknowns resolved:** driver choice — plan.md's file table assumed
  `psycopg2-binary`, but it has no prebuilt wheel for the local Python 3.14
  and failed to build from source. Switched to `psycopg[binary]==3.2.10`
  (psycopg3) and updated `DATABASE_URL` scheme to `postgresql+psycopg://` in
  `backend/app/core/config.py` and `.env.example`.
- **Verification:** `ruff check` clean on new files; models import and
  register on `Base.metadata` (`users`, `vendors`, `otps`, `refresh_tokens`);
  migration files compile; full `pytest` suite still passes (2 passed).
- **Files altered:** `pyproject.toml`, `.env.example`,
  `backend/app/core/config.py`, `backend/app/db/__init__.py`,
  `backend/app/db/session.py`, `backend/app/models/__init__.py`,
  `backend/app/models/user.py`, `backend/app/models/vendor.py`,
  `backend/app/models/otp.py`, `backend/app/models/refresh_token.py`,
  `alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`,
  `backend/migrations/versions/0001_create_auth_tables.py`.

## 2026-06-20 — Session 3: docker-compose PostGIS service

- **Context / goal:** `docker-compose.yml` (owned by feature 000-app-scaffold)
  had no DB service, so Phase 1's `DATABASE_URL` had nothing to connect to in
  Docker. User asked to add a Postgres+PostGIS service, persistent volume,
  port 5432, and a healthcheck gating backend startup.
- **Decisions:**
  - Used `postgis/postgis:16-3.4-alpine` (Postgres 16 + PostGIS 3.4 on
    Alpine) rather than plain `postgres:16-alpine`, since the latter has no
    PostGIS extension available — needed for `Vendor.shop_location`.
  - `db` service: `POSTGRES_DB=local_marketplace`, user/password `postgres`
    (matches `.env.example`); named volume `pgdata` for persistence; port
    `5432:5432` exposed; `pg_isready` healthcheck (5s interval/timeout, 5
    retries).
  - `backend` service: added `DATABASE_URL` pointing at `db:5432` (Docker
    network hostname, not `localhost`) and `depends_on: db: condition:
    service_healthy` so backend waits for the DB healthcheck.
  - Edit was additive only — existing `backend` service config untouched
    apart from the two new keys (Constitution P6).
- **Verification:** YAML parses correctly (`yaml.safe_load`).
- **Files altered:** `docker-compose.yml`.
