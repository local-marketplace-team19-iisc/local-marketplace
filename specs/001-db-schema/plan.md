# Plan — Feature 001: Db Schema (Dry-Run)

> **Iron-Clad Rule (Constitution P1 / SPEC §8):** this dry-run MUST be reviewed and
> **approved by the user** before any implementation file is created or modified.

## Scope

This document maps out the sequential, idempotent steps required to provision the local PostgreSQL environment, implement the code-first SQLAlchemy models, and establish the Alembic migration timeline.

## Milestone 1: Local Infrastructure Provisioning
- [ ] Create a local `.env` file containing explicit, un-hardcoded Postgres environment variables.
- [ ] Configure `docker-compose.yml` to pull a PostgreSQL 16 image bundled with PostGIS 3.4 and pgvector 0.5.x.
- [ ] Spin up the containerized layer via `docker compose up -d` and verify port 5432 availability.

## Milestone 2: Code-First Schema Architecture
- [ ] Initialize Alembic inside the project root utilizing the modern async environment configuration template.
- [ ] Implement the `DeclarativeBase` plumbing inside `db/base.py`.
- [ ] Write the 9 finalized tables in `db/models.py` using absolute SQLAlchemy 2.0 type mappings (`Mapped`, `mapped_column`).
- [ ] Embed structural constraints directly into the class definitions:
  - `CheckConstraint("stock_quantity >= 0")` on the Inventory model.
  - `UniqueConstraint("cart_id", "inventory_id")` on the CartLine model.
  - `GEOGRAPHY(Point, 4326)` spatial markers on the Vendor model.

## Milestone 3: Migration Lifecycle & Execution
- [ ] Update Alembic’s `env.py` to target the model metadata layer for clear autogeneration tracking.
- [ ] Inject raw SQL extension bootstrapping hooks into the migration template preamble:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE EXTENSION IF NOT EXISTS postgis;
  ```
- [ ] Generate the initial migration block: alembic revision --autogenerate -m "init_core_marketplace_schema".
- [ ] Execute the upgrade trail against the live container: alembic upgrade head.


## Milestone 4: Isolated Constraint Verification
[ ] Build a localized automated test script utilizing pytest and pytest-asyncio.

[ ] Assert that attempting to write a negative stock_quantity triggers an explicit IntegrityError.

[ ] Assert that attempting to duplicate a (cart_id, inventory_id) tuple fails the composite unique index rule.

[ ] Assert that alembic downgrade base completely clears out all custom tables and extension references cleanly.

---
**STATUS: AWAITING APPROVAL.** No implementation file will be created or modified
until this plan is approved by the user.
