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


2. **Scenario 2:** Deterministic ACID Checkout & Stock Decrementing
This scenario validates the transactional safety of the schema during the highest-risk phase of the application: converting a cart into a finalized order while safely managing shared inventory.

Given a user has a populated cart containing multiple cart_lines mapping to specific inventory items.

When the application initiates a checkout transaction to convert the cart into an order.

Then the system must atomically execute the following within a single SQLAlchemy session:

Generate a new orders header row, retrieving the auto-generated sequential order_number.

Create frozen order_lines rows bridging the orders, vendors, and inventory.

Decrement the stock_quantity on the corresponding inventory rows.

Delete the processed cart_lines.

Edge cases:

Concurrency (Race Condition): Two distinct users simultaneously attempt to checkout with the last remaining item of a specific inventory_id. The transaction must utilize SELECT ... FOR UPDATE row-level locking, and if the first transaction succeeds, the second must trigger an IntegrityError strictly enforced by the CHECK (stock_quantity >= 0) constraint on the inventory table.

Partial Transaction Failure: The database connection drops immediately after decrementing the inventory but before generating the orders row. The ACID transaction must fully rollback, restoring the stock_quantity and leaving the cart_lines intact.

Constraint Protection (Immutable Snapshot): Immediately after checkout, a vendor attempts to delete the inventory item that was just purchased. The database must block the deletion with an IntegrityError due to the ON DELETE RESTRICT rule defined on the order_lines table, protecting the historical receipt.

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

- Vector Embeddings (products): The embedding column on the products table correctly implements pgvector's VECTOR(384) type.

- Geospatial Types (vendors): The location column on the vendors table is configured to use the PostGIS GEOGRAPHY type.

- Pricing & Sort Index (inventory): The price column on the inventory table uses NUMERIC(10,2) with a CHECK (price >= 0) constraint and a dedicated B-Tree index on price to optimize the deterministic "cheapest-first" sort (master SPEC §2).

- Line Quantities (cart_lines, order_lines): Both line tables define quantity as INT with CHECK (quantity > 0) and a server_default of 1. cart_lines carries no price column — the cart-summary total is computed live from current inventory.price (volatile intent, not locked pricing); price is frozen only at checkout on order_lines.

- Frozen Snapshot (order_lines): order_lines carries purchase_price NUMERIC(10,2) with CHECK (purchase_price >= 0), copied from inventory.price at checkout time. A subsequent update to inventory.price MUST NOT alter any existing order_lines row — the (quantity, purchase_price) pair fully reconstructs the historical line total.

- Receipt Referential Integrity (order_lines): order_lines.inventory_id is NOT NULL with ON DELETE RESTRICT. Attempting to delete an inventory row referenced by any order_lines row MUST raise an IntegrityError; an order_lines row can never exist with a NULL inventory_id.

- Cart Cascade Chain (products → inventory → cart_lines): inventory.product_id and cart_lines.inventory_id both use ON DELETE CASCADE. Deleting a never-ordered product MUST cascade-delete its inventory rows and any referencing cart_lines (silently vanishing from active carts). Deleting a product whose inventory is referenced by order_lines MUST instead be blocked by the ON DELETE RESTRICT on order_lines.inventory_id.

- Identity Sequences (orders): The order_number on the orders model uses an explicitly defined sequential database Identity/SERIAL construct.

- Automated Timestamps (carts): The carts table successfully implements database-level hooks (e.g., server_default=func.now(), onupdate=func.now()) to manage volatile purchasing intent timestamps.

- Receipt Timestamp (orders): The orders table defines created_at as TIMESTAMP WITH TIME ZONE, NOT NULL, server_default=func.now(), with no onupdate hook — a DB-set, write-once timestamp consistent with the immutable receipt header.

- Extension Handling: The initial Alembic migration includes the raw SQL commands CREATE EXTENSION IF NOT EXISTS vector; and CREATE EXTENSION IF NOT EXISTS postgis; before attempting to construct the products or vendors tables.

- Clean Autogeneration: Running alembic revision --autogenerate produces the exact 9 tables with all specified foreign keys, without throwing type-recognition errors for PostGIS or pgvector.

- Reversibility: Running alembic downgrade base successfully drops all 9 tables, indexes, and custom types without leaving orphaned data structures in Postgres.


## 4. DB Schema Entities

The structured entity matrix for the 9 underlying tables managed through Alembic and versioned Python migration paths inside `db/migrations/`.

| Entity | Key fields (type) | Relationships | Notes (indexes / constraints) |
| :-- | :-- | :-- | :-- |
| **`users`** | `id` (UUID, PK)`email` (VARCHAR) | **1-to-Many:** `carts`**1-to-Many:** `orders` | Unique B-Tree index on `email` to enable rapid login identity lookups. |

| **`categories`** | `id` (UUID, PK)`name` (VARCHAR)`parent_category_id` (UUID, FK, Nullable)`description` (VARCHAR, Nullable) | **Many-to-1 (Self):** `categories` (via `parent_category_id`) **1-to-Many:** `products` | **Self-Referential Taxonomy Map** (resolves master SPEC's "pre-defined enum category"): the taxonomy is modeled as **admin-curated rows in this table, NOT a strict Postgres `ENUM` type** — so the category set is data-curated and extensible without a schema migration. The "enum" guarantee (vendors must pick from the pre-defined set) is enforced by the `products.category_id` FK pointing at an existing row, not by a DB enum.•&nbsp;*Parent Category:* `parent_category_id` is `NULL`. •&nbsp;*Subcategory:* `parent_category_id` contains the parent category's UUID. |

| **`products`** | `id` (UUID, PK)`category_id` (UUID, FK) | **Many-to-1:** `categories` **1-to-Many:** `inventory` | **Maps to Subcategory:** `category_id` points directly to the subcategory level row. Uses `ON DELETE RESTRICT`. `embedding` column leverages `VECTOR(384)` formatting. |

| **`vendors`** | `id` (UUID, PK)`location` (GEOGRAPHY) | **1-to-Many:** `inventory` | **Critical:** Geospatial `GiST` index defined directly over the PostGIS `location` coordinate vector. |

| **`inventory`** | `id` (UUID, PK)`vendor_id` (UUID, FK)`product_id` (UUID, FK)`price` (NUMERIC(10,2)) | **Many-to-1:** `vendors`**Many-to-1:** `products`**1-to-Many:** `cart_lines` | Resolves many-to-many catalog mappings. `stock_quantity` has a strict checker validation constraint: `CHECK (stock_quantity >= 0)`. `price` is `NUMERIC(10,2)` (₹, 2-decimal precision per master SPEC §2) with a `CHECK (price >= 0)` constraint and a **B-Tree index on `price`** to optimize the "cheapest-first" sort. `product_id` FK uses **`ON DELETE CASCADE`** so deleting a product removes its inventory rows, which in turn cascade to `cart_lines` — completing the `product → inventory → cart_lines` delete chain that lets a deleted product silently vanish from active carts. `vendor_id` FK uses `ON DELETE CASCADE` (deleting a vendor removes its inventory). **Note:** this cascade is still gated by `order_lines.inventory_id` `ON DELETE RESTRICT` — inventory referenced by any historical receipt cannot be deleted, so the cascade only fires for never-ordered inventory. |

| **`carts`** | `id` (UUID, PK)`user_id` (UUID, FK) | **Many-to-1:** `users`**1-to-Many:** `cart_lines` | Represents volatile customer purchasing intent. Updates default timestamp via database hooks. |

| **`cart_lines`** | `id` (UUID, PK)`cart_id` (UUID, FK)`inventory_id` (UUID, FK)`quantity` (INT) | **Many-to-1:** `carts`**Many-to-1:** `inventory` | Enforces a strict Unique Composite Constraint on columns `(cart_id, inventory_id)`. `quantity` is `INT` with `CHECK (quantity > 0)` and `server_default=1`; on duplicate add the quantity is incremented (Scenario 1). `inventory_id` FK uses **`ON DELETE CASCADE`** — a cart is volatile, uncommitted intent, so if a vendor deletes the underlying inventory/product the line silently vanishes from users' active carts (contrast with `order_lines`, which is an immutable receipt and uses `ON DELETE RESTRICT`). The `cart_id` FK uses `ON DELETE CASCADE` so deleting a cart clears its lines. **No price column:** the cart-summary total is computed live from the current `inventory.price` at render time. Price is frozen only at checkout (see `order_lines.purchase_price`). |

| **`orders`** | `id` (UUID, PK)`user_id` (UUID, FK)`order_number` (SERIAL/INT)`created_at` (TIMESTAMP WITH TIME ZONE) | **Many-to-1:** `users`**1-to-Many:** `order_lines` | Core immutable receipt header. `order_number` utilizes a sequential database Identity sequence generation schema. `created_at` is `TIMESTAMP WITH TIME ZONE`, NOT NULL, `server_default=func.now()` — a DB-set, write-once receipt timestamp (no `onupdate`, since the receipt is immutable). |

| **`order_lines`** | `id` (UUID, PK)`order_id` (UUID, FK)`vendor_id` (UUID, FK)`inventory_id` (UUID, FK, NOT NULL)`quantity` (INT)`purchase_price` (NUMERIC(10,2)) | **Many-to-1:** `orders`**Many-to-1:** `vendors`**Many-to-1:** `inventory` | Implements the frozen snapshot architectural pattern. `inventory_id` is **NOT NULL** with **`ON DELETE RESTRICT`** — a purchased inventory row can never be deleted while a receipt references it, so the link is always valid (resolves the prior nullable-vs-RESTRICT contradiction). `quantity` is `INT` with `CHECK (quantity > 0)` and `server_default=1`. `purchase_price` is `NUMERIC(10,2)` with `CHECK (purchase_price >= 0)` — the unit price **copied at checkout time**, so a later `inventory.price` update leaves this historical receipt untouched. The frozen pair `(quantity, purchase_price)` makes line/order totals reconstructable independently of live `inventory`. `ON DELETE RESTRICT` applies to all order links. |

## 5. System Constraints

- Database Engine: The system must run on PostgreSQL 16.x (or higher).

- Extension Versions: The database environment must support PostGIS 3.4+ and pgvector 0.5.x+.

- ORM Versioning: The Python application must utilize SQLAlchemy 2.0+ (specifically leveraging the modern 2.0 style syntax with Mapped and mapped_column) and Alembic 1.13+ for migrations.

- Driver (Async, mandated): The system MUST use `asyncpg` as the database driver and SQLAlchemy's `AsyncSession` (with `create_async_engine`) for all application data access — `psycopg2`/`psycopg3` synchronous paths are not permitted. The async URL scheme is `postgresql+asyncpg://...`. Relationship loading MUST avoid implicit lazy I/O under async (use `lazy='selectin'` / explicit eager loading). Alembic may run its migration scripts synchronously, but the application runtime is strictly async.

- Containerized Local DB: Local development must not rely on bare-metal Postgres installations. The local database must be provisioned via Docker (e.g., using a docker-compose.yml file) using an image that comes pre-packaged with PostGIS and pgvector (such as ankane/pgvector combined with PostGIS installations, or a custom Dockerfile).

- Environment Variables: Connection strings must not be hardcoded. The application and Alembic must dynamically construct the database URL via environment variables (e.g., POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT) loaded from a local .env file.

- Idempotent Setup: Developers must be able to spin up the entire database layer from scratch by running docker compose up -d followed by alembic upgrade head without manual SQL interventions.

## 5. Requirement Completeness / Definition of Done

This feature is DONE only when **all** hold:

- [x] No unresolved `[NEEDS CLARIFICATION]` markers remain (Constitution P2).
- [ ] `plan.md` was written and **user-approved** before any implementation (P1).
- [ ] All Functional Requirements (§2) have passing tests.
- [ ] All Success/Acceptance Criteria (§3) are met and verified.
- [ ] DB entities (§4) are migrated; schema matches the spec.
- [ ] `make test` green and `make lint` clean.
- [ ] Audit trail current: `spec.md`, `plan.md`, `prompts.md`, `conversation-history.md` all committed (P3).
- [ ] `docs/architecture.md` updated with any decision this feature introduced.
