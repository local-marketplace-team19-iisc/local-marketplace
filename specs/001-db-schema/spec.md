---
title: Feature 001: Db Schema
feature: 001-db-schema
status: draft
created: 2026-06-19
---

# Feature 001: Db Schema — Specification

> Architectural contract for feature `001-db-schema` (Constitution P3).
> Mark every unknown `[NEEDS CLARIFICATION: ...]` — never guess (Constitution P2).
> Outranked by `specs/constitution.md` and the master `SPEC.md`.

## 1. User Scenarios & Edge Cases

Primary scenarios (Given / When / Then), each with the edge cases it must handle.

1. **Scenario 1:** Cart Management & Composite Constraint Validation

This scenario validates the schema's ability to maintain data integrity when users interact with their shopping carts, specifically testing foreign key constraints and the composite unique constraint on cart_lines.

Given a user has an active carts record and wants to add a specific product from a vendor.

When the system attempts to insert a new row into the cart_lines table.

Then the database must successfully create the relationship mapping the cart_id to the inventory_id.

Edge cases:

Duplicate Insertion (Concurrency/Retry): The user clicks "Add to Cart" twice rapidly. The database must reject the second insertion via an IntegrityError triggered by the Unique Composite Constraint on (cart_id, inventory_id), rather than creating duplicate lines. Instead the lines
quantity is updated in cart.

Orphaned Inventory (Not-Found): The inventory_id provided no longer exists. The database must reject the insert via a Foreign Key constraint violation.

Cart Limits: The user attempts to add an excessive number of unique cart_lines (e.g., >100), testing database payload limits and indexing performance on the cart_lines.cart_id foreign key.


2. **Scenario 2:** Schema Guarantees that Enable Deterministic ACID Checkout

> **Scope note:** application-level transactional orchestration — `SELECT ... FOR UPDATE` locking, SQLAlchemy session management, and the execution ordering of the checkout steps — is **explicitly out of scope for this schema feature** and is owned by a later checkout/orders feature. This scenario validates only the **schema-level guarantees** (constraints, defaults, FK delete rules, frozen-snapshot columns) that make a correct checkout *possible*; it does not specify how the application drives the transaction.

This scenario validates that the schema, by itself, provides the integrity guarantees the highest-risk phase (converting a cart into a finalized order over shared inventory) will rely on.

Given a populated cart with cart_lines mapping to specific inventory items, and the schema as defined in §4.

When rows are written/updated/deleted across orders, order_lines, inventory, and cart_lines (by whatever orchestration a later feature implements).

Then the schema MUST guarantee, independently of application logic:

`orders.order_number` is DB-assigned (`GENERATED ALWAYS AS IDENTITY`) and `UNIQUE`.

`order_lines` can persist a frozen snapshot — `(quantity, purchase_price)` — so the receipt total is reconstructable even after `inventory.price` later changes.

The `CHECK (stock_quantity >= 0)` constraint makes overselling impossible at the database level.

Schema-guarantee edge cases:

Oversell Floor (outcome, not mechanism): If two checkouts both try to consume the last unit of an inventory_id, the `CHECK (stock_quantity >= 0)` constraint MUST reject whichever decrement would drive stock below zero (raising an IntegrityError). *How* the application serializes the two attempts (locking, retries) is out of scope.

Atomicity Readiness: The schema MUST be safe to mutate within a single ACID transaction — constraints and FKs are defined such that a mid-transaction failure can roll back to a consistent state with no orphaned rows. The transaction control itself is out of scope.

Constraint Protection (Immutable Snapshot): A vendor attempting to delete an inventory item referenced by any order_lines row MUST be blocked with an IntegrityError, enforced by the `ON DELETE RESTRICT` rule on `order_lines.inventory_id`, protecting the historical receipt.

## 2. Functional Requirements & Decisions

Each requirement is testable; each records the decision taken (and why) so the
"how" is auditable. Open points stay `[NEEDS CLARIFICATION]`.

| ID | Requirement (MUST/SHOULD) | Decision taken & rationale |
| :-- | :-- | :-- |
| FR-1 | The system must use SQLAlchemy ORM (Declarative Base) as the single source of truth to define all database tables, columns, constraints, and relationships in Python code.| If there is any schema that is not defined completely or has missing info must be flagged out |

| FR-2 | The system must use Alembic to track all database schema changes. Every modification to the database structure must be captured as a sequential, version-controlled Python migration script stored in the db/migrations/ directory.|

| FR-3 |The initial migration must explicitly verify and install required Postgres extensions (pgvector and postgis) before attempting to construct the schema tables.|

## 3. Success Criteria / Acceptance Criteria

Objective, verifiable criteria that mark this feature "done & correct".

- All models inherit from a central DeclarativeBase (if using SQLAlchemy 2.0) or declarative_base().

- Type Mapping: All columns are defined with strict types (e.g., using Mapped[int], mapped_column(String(255))) that correctly map to the underlying database dialect.

- Constraints Applied: Nullable, Unique, and CheckConstraint rules are explicitly defined on all required columns to prevent bad data at the database level.

- Relationships & Cascades: Foreign keys are explicitly defined. relationship() directives are configured with appropriate loading strategies (e.g., lazy='selectin') and cascade behaviors (e.g., cascade="all, delete-orphan" where appropriate).

- UUID Primary Keys: All 9 models (users, categories, products, vendors, inventory, carts, cart_lines, orders, order_lines) are confirmed to use UUID fields as their primary keys.

- Self-Referential Taxonomy: The categories model correctly implements a Many-to-1 self-referential relationship (parent_category_id maps to categories.id and accepts NULL).

- Vector Embeddings (products): products defines name VARCHAR(255) NOT NULL and description TEXT Nullable. The embedding column is pgvector VECTOR(384), populated from the deterministic template "Product: {name}. Description: {description}" using the pinned bge-small-en-v1.5 model (or equivalent lightweight transformer emitting exactly 384 dims). A database-level HNSW index using cosine distance (vector_cosine_ops) is defined on embedding; query plans for semantic search MUST use the HNSW index — sequential scans over embedding are banned.

- Geospatial Types (vendors): The location column on the vendors table is GEOGRAPHY(Point, 4326) (SRID 4326, WGS 84 lon/lat degrees), with a GiST index defined over it. Proximity queries (ST_DWithin) return distances in meters natively, with no manual projection, to serve the 5km radius search.

- Credential Storage (users): The password_hash column on the users table is VARCHAR(255), NOT NULL, and stores a one-way salted hash (bcrypt/argon2). Plaintext passwords MUST NOT be stored anywhere; authentication hashes the submitted password and compares hashes in constant time — the stored value is never decrypted.

- Stock Quantity (inventory): The stock_quantity column on the inventory table is INTEGER, NOT NULL, server_default=0, with a CHECK (stock_quantity >= 0) constraint that enforces the non-negative floor relied on by the Scenario 2 checkout race condition.

- Pricing & Sort Index (inventory): The price column on the inventory table uses NUMERIC(10,2) with a CHECK (price >= 0) constraint and a dedicated B-Tree index on price to optimize the deterministic "cheapest-first" sort (master SPEC §2).

- Line Quantities (cart_lines, order_lines): Both line tables define quantity as INT with CHECK (quantity > 0) and a server_default of 1. cart_lines carries no price column — the cart-summary total is computed live from current inventory.price (volatile intent, not locked pricing); price is frozen only at checkout on order_lines.

- Frozen Snapshot (order_lines): order_lines carries purchase_price NUMERIC(10,2) with CHECK (purchase_price >= 0), copied from inventory.price at checkout time. A subsequent update to inventory.price MUST NOT alter any existing order_lines row — the (quantity, purchase_price) pair fully reconstructs the historical line total.

- Receipt Referential Integrity (order_lines): order_lines.inventory_id is NOT NULL with ON DELETE RESTRICT. Attempting to delete an inventory row referenced by any order_lines row MUST raise an IntegrityError; an order_lines row can never exist with a NULL inventory_id.

- Cart Cascade Chain (products → inventory → cart_lines): inventory.product_id and cart_lines.inventory_id both use ON DELETE CASCADE. Deleting a never-ordered product MUST cascade-delete its inventory rows and any referencing cart_lines (silently vanishing from active carts). Deleting a product whose inventory is referenced by order_lines MUST instead be blocked by the ON DELETE RESTRICT on order_lines.inventory_id.

- Identity Sequences (orders): The order_number on the orders model is declared INTEGER GENERATED ALWAYS AS IDENTITY (not legacy SERIAL), NOT NULL, with a strict UNIQUE constraint (unique B-Tree index). The database always assigns the value — a client-supplied order_number MUST be rejected (GENERATED ALWAYS), and a duplicate MUST raise an IntegrityError.

- Automated Timestamps (carts): The carts table declares created_at (TIMESTAMP WITH TIME ZONE, NOT NULL, server_default=func.now(), write-once) and updated_at (TIMESTAMP WITH TIME ZONE, NOT NULL, server_default=func.now(), onupdate=func.now()). The DB-level hooks set created_at on insert and refresh updated_at on every row change, with no application-side timestamp management.

- Receipt Timestamp (orders): The orders table defines created_at as TIMESTAMP WITH TIME ZONE, NOT NULL, server_default=func.now(), with no onupdate hook — a DB-set, write-once timestamp consistent with the immutable receipt header.

- Extension Handling: The initial Alembic migration includes the raw SQL commands CREATE EXTENSION IF NOT EXISTS vector; and CREATE EXTENSION IF NOT EXISTS postgis; before attempting to construct the products or vendors tables.

- Clean Autogeneration: Running alembic revision --autogenerate produces the exact 9 tables with all specified foreign keys, without throwing type-recognition errors for PostGIS or pgvector.

- Reversibility: Running alembic downgrade base successfully drops all 9 tables, indexes, and custom types without leaving orphaned data structures in Postgres.


## 4. DB Schema Entities

The structured entity matrix for the 9 underlying tables managed through Alembic and versioned Python migration paths inside `db/migrations/`.

| Entity | Key fields (type) | Relationships | Notes (indexes / constraints) |
| :-- | :-- | :-- | :-- |
| **`users`** | `id` (UUID, PK)`email` (VARCHAR)`password_hash` (VARCHAR(255)) | **1-to-Many:** `carts`**1-to-Many:** `orders` | Unique B-Tree index on `email` to enable rapid login identity lookups. `password_hash` is `VARCHAR(255)`, `NOT NULL`, and stores a **one-way salted hash** (bcrypt/argon2 — the algorithm + per-user salt are encoded in the stored string). **It is NOT reversible encryption:** login NEVER decrypts the stored value; it hashes the submitted password with the same scheme and compares the resulting hashes (constant-time). The plaintext password is never stored, logged, or recoverable. |

| **`categories`** | `id` (UUID, PK)`name` (VARCHAR)`parent_category_id` (UUID, FK, Nullable)`description` (VARCHAR, Nullable) | **Many-to-1 (Self):** `categories` (via `parent_category_id`) **1-to-Many:** `products` | **Self-Referential Taxonomy Map** (resolves master SPEC's "pre-defined enum category"): the taxonomy is modeled as **admin-curated rows in this table, NOT a strict Postgres `ENUM` type** — so the category set is data-curated and extensible without a schema migration. The "enum" guarantee (vendors must pick from the pre-defined set) is enforced by the `products.category_id` FK pointing at an existing row, not by a DB enum.•&nbsp;*Parent Category:* `parent_category_id` is `NULL`. •&nbsp;*Subcategory:* `parent_category_id` contains the parent category's UUID. |

| **`products`** | `id` (UUID, PK)`category_id` (UUID, FK → `categories.id`, ON DELETE RESTRICT)`name` (VARCHAR(255), NOT NULL)`description` (TEXT, Nullable)`embedding` (VECTOR(384)) | **Many-to-1:** `categories` **1-to-Many:** `inventory` | **Maps to Subcategory:** `category_id` points to the subcategory row; the `category_id → categories.id` FK uses **`ON DELETE RESTRICT`** — a category that still has products cannot be deleted, protecting the taxonomy from orphaning live catalog rows. **Semantic search payload:** the text fed to the embedding pipeline is the deterministic template `"Product: {name}. Description: {description}"` (with `{description}` rendered empty when NULL), so embeddings are reproducible from `(name, description)`. **Embedding model is pinned** to `bge-small-en-v1.5` (or an equivalent lightweight transformer) which emits **exactly 384 dimensions** → `embedding` is `VECTOR(384)`. **Index:** a database-level **HNSW** index is defined on `embedding` using **cosine distance** (`vector_cosine_ops`); sequential scans over `embedding` are banned (required for the <500ms latency NFR, master SPEC §6). |

| **`vendors`** | `id` (UUID, PK)`location` (GEOGRAPHY(Point, 4326)) | **1-to-Many:** `inventory` | **Critical:** `location` is `GEOGRAPHY(Point, 4326)` — SRID 4326 (WGS 84 lon/lat degrees), so `ST_DWithin`/distance calculations are natively in meters over longitude/latitude without manual projection. A geospatial **`GiST`** index is defined directly over `location` to serve the 5km proximity search (master SPEC §2). |

| **`inventory`** | `id` (UUID, PK)`vendor_id` (UUID, FK)`product_id` (UUID, FK)`price` (NUMERIC(10,2))`stock_quantity` (INTEGER) | **Many-to-1:** `vendors`**Many-to-1:** `products`**1-to-Many:** `cart_lines` | Resolves many-to-many catalog mappings. `stock_quantity` is `INTEGER`, `NOT NULL`, `server_default=0`, with a strict checker validation constraint: `CHECK (stock_quantity >= 0)` (enforces the Scenario 2 concurrency floor). `price` is `NUMERIC(10,2)` (₹, 2-decimal precision per master SPEC §2) with a `CHECK (price >= 0)` constraint and a **B-Tree index on `price`** to optimize the "cheapest-first" sort. `product_id` FK uses **`ON DELETE CASCADE`** so deleting a product removes its inventory rows, which in turn cascade to `cart_lines` — completing the `product → inventory → cart_lines` delete chain that lets a deleted product silently vanish from active carts. `vendor_id` FK uses `ON DELETE CASCADE` (deleting a vendor removes its inventory). **Note:** this cascade is still gated by `order_lines.inventory_id` `ON DELETE RESTRICT` — inventory referenced by any historical receipt cannot be deleted, so the cascade only fires for never-ordered inventory. |

| **`carts`** | `id` (UUID, PK)`user_id` (UUID, FK)`created_at` (TIMESTAMP WITH TIME ZONE)`updated_at` (TIMESTAMP WITH TIME ZONE) | **Many-to-1:** `users`**1-to-Many:** `cart_lines` | Represents volatile customer purchasing intent. `created_at` is `TIMESTAMP WITH TIME ZONE`, NOT NULL, `server_default=func.now()` (write-once). `updated_at` is `TIMESTAMP WITH TIME ZONE`, NOT NULL, `server_default=func.now()` **and** `onupdate=func.now()` — the DB refreshes it on every row change to track volatile purchasing intent. Both are DB-managed hooks, not application-set. |

| **`cart_lines`** | `id` (UUID, PK)`cart_id` (UUID, FK)`inventory_id` (UUID, FK)`quantity` (INT) | **Many-to-1:** `carts`**Many-to-1:** `inventory` | Enforces a strict Unique Composite Constraint on columns `(cart_id, inventory_id)`. `quantity` is `INT` with `CHECK (quantity > 0)` and `server_default=1`; on duplicate add the quantity is incremented (Scenario 1). `inventory_id` FK uses **`ON DELETE CASCADE`** — a cart is volatile, uncommitted intent, so if a vendor deletes the underlying inventory/product the line silently vanishes from users' active carts (contrast with `order_lines`, which is an immutable receipt and uses `ON DELETE RESTRICT`). The `cart_id` FK uses `ON DELETE CASCADE` so deleting a cart clears its lines. **No price column:** the cart-summary total is computed live from the current `inventory.price` at render time. Price is frozen only at checkout (see `order_lines.purchase_price`). |

| **`orders`** | `id` (UUID, PK)`user_id` (UUID, FK)`order_number` (INTEGER GENERATED ALWAYS AS IDENTITY)`created_at` (TIMESTAMP WITH TIME ZONE) | **Many-to-1:** `users`**1-to-Many:** `order_lines` | Core immutable receipt header. `order_number` is declared `INTEGER GENERATED ALWAYS AS IDENTITY` (modern SQL identity, not legacy `SERIAL`) and carries a **strict `UNIQUE` constraint** (backed by a unique B-Tree index), `NOT NULL` — the database always assigns the value (manual inserts are rejected), guaranteeing the "one unique order number" promise (master SPEC §3). `created_at` is `TIMESTAMP WITH TIME ZONE`, NOT NULL, `server_default=func.now()` — a DB-set, write-once receipt timestamp (no `onupdate`, since the receipt is immutable). |

| **`order_lines`** | `id` (UUID, PK)`order_id` (UUID, FK)`vendor_id` (UUID, FK)`inventory_id` (UUID, FK, NOT NULL)`quantity` (INT)`purchase_price` (NUMERIC(10,2)) | **Many-to-1:** `orders`**Many-to-1:** `vendors`**Many-to-1:** `inventory` | Implements the frozen snapshot architectural pattern. `inventory_id` is **NOT NULL** with **`ON DELETE RESTRICT`** — a purchased inventory row can never be deleted while a receipt references it, so the link is always valid (resolves the prior nullable-vs-RESTRICT contradiction). `quantity` is `INT` with `CHECK (quantity > 0)` and `server_default=1`. `purchase_price` is `NUMERIC(10,2)` with `CHECK (purchase_price >= 0)` — the unit price **copied at checkout time**, so a later `inventory.price` update leaves this historical receipt untouched. The frozen pair `(quantity, purchase_price)` makes line/order totals reconstructable independently of live `inventory`. `ON DELETE RESTRICT` applies to all order links. |

## 5. System Constraints

- Database Engine: The system must run on PostgreSQL 16.x (or higher).

- Extension Versions: The database environment must support PostGIS 3.4+ and pgvector 0.5.x+.

- Embedding Model (pinned): Semantic search MUST use the pinned `bge-small-en-v1.5` embedding model (or an equivalent lightweight transformer emitting exactly 384 dimensions), matching the `products.embedding VECTOR(384)` column. The text payload is the deterministic template `"Product: {name}. Description: {description}"`. The `embedding` column MUST be served by a database-level HNSW index using cosine distance (`vector_cosine_ops`); sequential scans over `embedding` are banned.

- ORM Versioning: The Python application must utilize SQLAlchemy 2.0+ (specifically leveraging the modern 2.0 style syntax with Mapped and mapped_column) and Alembic 1.13+ for migrations.

- Driver (Async, mandated): The system MUST use `asyncpg` as the database driver and SQLAlchemy's `AsyncSession` (with `create_async_engine`) for all application data access — `psycopg2`/`psycopg3` synchronous paths are not permitted. The async URL scheme is `postgresql+asyncpg://...`. Relationship loading MUST avoid implicit lazy I/O under async (use `lazy='selectin'` / explicit eager loading). Alembic may run its migration scripts synchronously, but the application runtime is strictly async.

- Containerized Local DB: Local development must not rely on bare-metal Postgres installations. The local database must be provisioned via Docker (e.g., using a docker-compose.yml file) using an image that comes pre-packaged with PostGIS and pgvector (such as ankane/pgvector combined with PostGIS installations, or a custom Dockerfile).

- Environment Variables: Connection strings must not be hardcoded. The application and Alembic must dynamically construct the database URL via environment variables (e.g., POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT) loaded from a local .env file.

- Idempotent Setup: Developers must be able to spin up the entire database layer from scratch by running docker compose up -d followed by alembic upgrade head without manual SQL interventions.

## 6. Requirement Completeness / Definition of Done

This feature is DONE only when **all** hold:

- [ ] No unresolved `[NEEDS CLARIFICATION]` markers remain (Constitution P2). <!-- BLOCKED: plan.md is still all [NEEDS CLARIFICATION] (Scope, Files, decisions, risks, verification). -->
- [ ] `plan.md` was written and **user-approved** before any implementation (P1).
- [ ] All Functional Requirements (§2) have passing tests.
- [ ] All Success/Acceptance Criteria (§3) are met and verified.
- [ ] DB entities (§4) are migrated; schema matches the spec.
- [ ] `make test` green and `make lint` clean.
- [ ] Audit trail current: `spec.md`, `plan.md`, `prompts.md`, `conversation-history.md` all committed (P3).
- [ ] `docs/architecture.md` updated with any decision this feature introduced.
