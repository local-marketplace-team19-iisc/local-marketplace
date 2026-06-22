# Plan — Feature 001: Db Schema (Dry-Run)

> **Iron-Clad Rule (Constitution P1 / SPEC §8):** this dry-run MUST be reviewed and
> **approved by the user** before any implementation file is created or modified.

## Scope

This document maps out the sequential, idempotent steps required to provision the local PostgreSQL environment, implement the code-first SQLAlchemy models, and establish the Alembic migration timeline.

## Milestone 1: Local Infrastructure Provisioning ✅ COMPLETE
> **Runtime note:** `docker compose` is not available; the container runtime on this machine is **Podman 5.5+**. All `docker compose` references below map to equivalent `podman` commands (see `make docker-build` / `make docker-up`). Image pulls require `env -u HTTP_PROXY -u HTTPS_PROXY` to bypass an unreachable corporate proxy; build RUN steps pass `--build-arg http_proxy=...` to use the proxy for apt/pip inside the container.

- [x] Create a local `.env` file containing explicit, un-hardcoded Postgres environment variables.
- [x] Create `backend/db/Dockerfile` — a custom DB image that layers pgvector onto the official PostGIS image (`FROM --platform=linux/amd64 postgis/postgis:16-3.4`).
- [x] Update `docker-compose.yml` to build from this Dockerfile and expose port 5432.
- [x] Create `backend/db/init/01-extensions.sql` with idempotent `CREATE EXTENSION IF NOT EXISTS vector/postgis`.
- [x] Update `docker-compose.yml` to mount init SQL into `/docker-entrypoint-initdb.d/`.
- [x] Spin up DB container via `make docker-up` (`podman run -d --name marketplace-db ...`) and verify port 5432.
- [x] Verify extensions: `podman exec marketplace-db psql -U marketplace -d marketplace -c "\dx"` confirmed `postgis 3.4.3` and `vector 0.8.3` active.

## Milestone 2: Code-First Schema Architecture
> **Migration path note:** A prior migration chain at `backend/migrations/` (revisions 0001-0003) covers auth tables from features 002/003. The 001-db-schema feature creates a **separate** Alembic chain at `backend/db/migrations/` for the 9 marketplace entities — `alembic.ini`'s `script_location` is updated to `backend/db/migrations/`.

- [x] Update `pyproject.toml` with all packages (`sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pgvector`, `geoalchemy2`, `pytest-asyncio`) and `asyncio_mode = "auto"`.
- [ ] Run `alembic init backend/db/migrations` from the project root. Creates scaffold and sets `script_location = backend/db/migrations` in `alembic.ini`.
- [ ] Create the `backend/app/models/` package with three files:
  - `backend/app/models/base.py` — declares the SQLAlchemy `DeclarativeBase` metadata class.
  - `backend/app/models/models.py` — implements all 9 production table entity classes using SQLAlchemy 2.0 `Mapped` / `mapped_column` syntax.
  - `backend/app/models/__init__.py` — exports all model classes for clean application-wide imports (e.g. `from app.models import User`).
- [ ] Create `backend/app/db/session.py` — the application-wide async engine and session factory:
  - Construct the async database URL from environment variables using `postgresql+asyncpg://`.
  - Instantiate `create_async_engine(url, echo=False)` as the module-level engine singleton.
  - Expose `AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)` as the session factory.
  - Provide a `get_db()` async generator for FastAPI dependency injection.
- [ ] Implement async runner hooks in `backend/db/migrations/env.py`:
  - Import `target_metadata` from `backend/app/models/base.py`.
  - Register custom type renderers for pgvector and geoalchemy2 via Alembic's `render_item` hook. Without this, `--autogenerate` silently emits a generic `LargeBinary` type for `VECTOR(384)` and `NullType` for `GEOGRAPHY` — the migration runs clean but produces the wrong DDL. The hook must map `pgvector.sqlalchemy.Vector` → `"Vector(<dims>)"` and `geoalchemy2.types.Geography` → `"Geography(<geometry_type>, <srid>)"` in the generated migration source.
  - Define `run_migrations_online()` using `asyncio.run()` wrapping an inner `run_async_migrations()` coroutine that calls `async_engine_from_config()` and executes migrations within an `AsyncConnection`.
  - Ensure the synchronous `run_migrations_offline()` path remains intact for environments that don't require a live connection.
- [ ] Embed all structural constraints and indexes directly into the class definitions:
  - **CHECK constraints:** `CHECK (stock_quantity >= 0)` on `Inventory`; `CHECK (price >= 0)` on `Inventory`; `CHECK (quantity > 0)` on `CartLine` and `OrderLine`; `CHECK (purchase_price >= 0)` on `OrderLine`.
  - **UNIQUE constraints:** `UniqueConstraint("cart_id", "inventory_id")` on `CartLine`; `UniqueConstraint("user_id")` on `Cart` (one cart per user); unique B-Tree index on `User.email`, `Category.name`, `Order.order_number`.
  - **Geospatial / vector indexes:** `GEOGRAPHY(Point, 4326)` + GiST index on `Vendor.location`; HNSW index (`vector_cosine_ops`) on `Product.embedding`; B-Tree index on `Inventory.price`.
  - **Identity sequence:** `GENERATED ALWAYS AS IDENTITY` on `Order.order_number`.
  - **FK delete rules:**
    - CASCADE: `Cart.user_id`, `CartLine.cart_id`, `CartLine.inventory_id`, `Inventory.product_id`, `Inventory.vendor_id`, `OrderLine.order_id`.
    - RESTRICT: `OrderLine.inventory_id`, `OrderLine.product_id`, `OrderLine.vendor_id`, `Product.category_id`.
    - SET NULL: `Order.user_id`.
  - **Server defaults:** `server_default=func.now()` on `Cart.created_at`, `Cart.updated_at`, `Order.created_at`; `server_default=0` on `Inventory.stock_quantity`; `server_default=1` on `CartLine.quantity` and `OrderLine.quantity`.
  - **ORM-level onupdate:** `onupdate=func.now()` on `Cart.updated_at` — fires only through active SQLAlchemy sessions; direct SQL bypasses it (accepted trade-off, documented in spec §3).
  - **Relationship loading:** every `relationship()` directive must use `lazy='selectin'`; implicit lazy-load under asyncpg raises `MissingGreenlet` at runtime and will not be caught by unit tests.
  - **Primary key type:** all 9 models use `mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)` — plain `String` UUID will serialize as a string and break `UUID`-typed FK joins.
  - **Inventory.price NOT NULL:** `price NUMERIC(10,2) NOT NULL` — a listed item must have a price; omitting `NOT NULL` here allows NULL prices to silently pass the `CHECK (price >= 0)` constraint.

## Milestone 3: Migration Lifecycle & Execution
- [ ] Verify `env.py` wiring: confirm `target_metadata = Base.metadata` is set, the `run_async_migrations` coroutine binds correctly to `async_engine_from_config()`, and `alembic revision --autogenerate` detects all 9 tables without type-recognition errors for PostGIS or pgvector types.
- [ ] Generate the initial migration block: `alembic revision --autogenerate -m "init_core_marketplace_schema"`.
- [ ] Open the generated file in `backend/db/migrations/versions/` and manually edit it — autogenerate does **not** emit extensions or custom indexes:
  - Add at the **top of `upgrade()`** (before any `CREATE TABLE`): `op.execute("CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS postgis;")`.
  - Add HNSW index on `products.embedding`: `op.create_index("ix_products_embedding_hnsw", "products", ["embedding"], postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"})`.
  - Add GiST index on `vendors.location`: `op.create_index("ix_vendors_location_gist", "vendors", ["location"], postgresql_using="gist")`.
  - Add to **`downgrade()`** (before any `DROP TABLE`): `op.drop_index("ix_products_embedding_hnsw", table_name="products")` and `op.drop_index("ix_vendors_location_gist", table_name="vendors")`.
  - Add at the **end of `downgrade()`**: `op.execute("DROP EXTENSION IF EXISTS vector; DROP EXTENSION IF EXISTS postgis;")`.
  Do NOT inject extension SQL into `script.py.mako` — that would pollute every future migration.
- [ ] Execute the upgrade trail against the live container: `alembic upgrade head`.


## Milestone 4: Isolated Constraint Verification

Build a localized automated test suite using `pytest` and `pytest-asyncio` against a live test database. Each assertion must trigger the exact DB-level error — no mocking of constraints.

**Test infrastructure**
- [ ] Create `backend/tests/conftest.py` with an async `async_session` fixture that:
  - Reads `TEST_DATABASE_URL` from the environment (separate from the dev DB URL, so test runs never mutate the development database).
  - Before the test session: creates all tables via `async_engine.begin()` + `Base.metadata.create_all`.
  - After the test session: drops all tables via `Base.metadata.drop_all`.
  Add `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/marketplace_test` (or equivalent placeholder) to `.env.example`.

**CHECK constraint assertions**
- [ ] Insert `Inventory` with `stock_quantity = -1` → raises `IntegrityError` (`CHECK (stock_quantity >= 0)`).
- [ ] Insert `Inventory` with `price = -0.01` → raises `IntegrityError` (`CHECK (price >= 0)`).
- [ ] Insert `CartLine` with `quantity = 0` → raises `IntegrityError` (`CHECK (quantity > 0)`).
- [ ] Insert `OrderLine` with `quantity = 0` → raises `IntegrityError` (`CHECK (quantity > 0)`).
- [ ] Insert `OrderLine` with `purchase_price = -1` → raises `IntegrityError` (`CHECK (purchase_price >= 0)`).

**UNIQUE constraint assertions**
- [ ] Insert two `CartLine` rows with the same `(cart_id, inventory_id)` → raises `IntegrityError` (composite unique constraint).
- [ ] Insert a second `Cart` row for the same `user_id` → raises `IntegrityError` (`UNIQUE` on `carts.user_id`).
- [ ] Insert a second `User` with a duplicate `email` → raises `IntegrityError` (`UNIQUE` on `users.email`).

**FK ON DELETE CASCADE assertions**
- [ ] Delete an `Order` row → its child `OrderLine` rows are automatically removed (cascade verified by follow-up SELECT).
- [ ] Delete a `User` row → their `Cart` and all associated `CartLine` rows are automatically removed.

**FK ON DELETE RESTRICT assertions**
- [ ] Attempt to delete an `Inventory` row referenced by an `OrderLine` → raises `IntegrityError` (`ON DELETE RESTRICT` on `order_lines.inventory_id`).
- [ ] Attempt to delete a `Product` row referenced by an `OrderLine` → raises `IntegrityError` (`ON DELETE RESTRICT` on `order_lines.product_id`).
- [ ] Attempt to delete a `Vendor` row referenced by an `OrderLine` → raises `IntegrityError` (`ON DELETE RESTRICT` on `order_lines.vendor_id`).
- [ ] Attempt to delete a `Category` row that has associated `Product` rows → raises `IntegrityError` (`ON DELETE RESTRICT` on `products.category_id`).

**FK ON DELETE CASCADE (product/vendor/inventory chain) assertions**
- [ ] Delete a `Product` row that has never been ordered → its `Inventory` rows are automatically removed (cascade verified by a follow-up SELECT on `inventory`).
- [ ] Delete a `Vendor` row whose inventory rows have never been ordered → its `Inventory` rows are automatically removed (cascade verified by follow-up SELECT).

**Additional UNIQUE assertion**
- [ ] Insert a second `Category` row with a duplicate `name` → raises `IntegrityError` (`UNIQUE` on `categories.name`).

**FK ON DELETE SET NULL assertion**
- [ ] Delete a `User` row that owns one or more `Order` rows → `orders.user_id` is set to `NULL`; the `Order` rows themselves are retained.

**Nullable / identity assertions**
- [ ] Insert a `Product` row without providing `embedding` → insert succeeds; `embedding` column is `NULL` (async/deferred pipeline allowed).
- [ ] Insert an `Order` row with a client-supplied `order_number` → raises `IntegrityError` or `ProgrammingError` (`GENERATED ALWAYS AS IDENTITY` rejects client-supplied values).

**Reversibility assertion**
- [ ] Run `alembic downgrade base` against the live test DB → all 9 tables, custom indexes, and extension references are dropped with no orphaned structures remaining.

---
**STATUS: APPROVED** No implementation file will be created or modified
until this plan is approved by the user.
