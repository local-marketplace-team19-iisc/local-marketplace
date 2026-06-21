# Conversation History — Feature 001: Db Schema

Append-only, cumulative log of every working session on this feature
(Constitution P3 & P7). Earlier entries are NEVER overwritten or truncated.
Each entry: context/goal · decisions + reasoning · edge cases / unknowns ·
`[NEEDS CLARIFICATION]` raised or resolved · files altered.

---

## 2026-06-19 — Session 1: Feature scaffolding

- **Context / goal:** Initialise feature `001-db-schema` via `/spec-create`.
- **Decisions:** Created `specs/001-db-schema/` with `spec.md`, `plan.md`, `prompts.md`,
  `conversation-history.md`; set `.active_feature` → `001-db-schema` (P7).
- **Unknowns raised:** spec.md & plan.md seeded with `[NEEDS CLARIFICATION]` markers
  to be resolved with the user before any implementation (P1, P2).
- **Files altered:** new feature folder + `.active_feature`.

---

## 2026-06-21 — Session 2: Spec validation & schema hardening

- **Context / goal:** Validate `spec.md` against the constitution + master `SPEC.md`,
  then resolve every finding with the user, one decision at a time. Author a reusable
  `review-spec` skill and re-run it.

- **Decisions made & reasoning:**
  - **Pricing model = live → live → frozen.** Added `inventory.price NUMERIC(10,2)`
    (`CHECK >= 0`, B-Tree index) for the master-SPEC "cheapest-first" sort. Cart stays
    *unpriced* (volatile intent — total computed live from `inventory.price`); price is
    frozen only at checkout via `order_lines.purchase_price NUMERIC(10,2)` (`CHECK >= 0`).
    Briefly added then **removed** `cart_lines.price` once the volatile-intent rule was set.
  - **Line quantities.** `cart_lines.quantity` & `order_lines.quantity` → `INT`,
    `CHECK (quantity > 0)`, `server_default=1`.
  - **Frozen snapshot completed.** `(quantity, purchase_price)` on `order_lines` make
    the receipt reconstructable after later `inventory.price` changes.
  - **Receipt referential integrity (#8 resolved).** `order_lines.inventory_id` →
    **NOT NULL + ON DELETE RESTRICT** (was the nullable+RESTRICT contradiction).
  - **Driver fork resolved.** Mandated `asyncpg` + SQLAlchemy `AsyncSession`; sync paths
    banned; Alembic may run sync.
  - **Category fork resolved.** Keep the self-referential `categories` table; drop the
    strict Postgres `ENUM` (admin-curated rows; FK enforces the "pre-defined set").
  - **Delete-cascade chain.** `cart_lines.inventory_id`, `inventory.product_id`,
    `inventory.vendor_id` → ON DELETE CASCADE so a deleted product/vendor silently
    vanishes from volatile carts — **gated** by `order_lines` RESTRICT (ordered inventory
    can't be deleted; receipts win).
  - **Timestamps.** `orders.created_at TIMESTAMPTZ`, NOT NULL, `server_default=now()`,
    write-once (no `onupdate`) for the immutable receipt.
  - **Core columns added.** `inventory.stock_quantity INTEGER NOT NULL default 0
    CHECK >= 0` (was referenced everywhere but undeclared — critical blocker).
  - **Auth.** Master `SPEC.md` switched from mobile OTP → **email-based login**. Added
    `users.password_hash VARCHAR(255) NOT NULL` storing a **one-way salted hash**
    (bcrypt/argon2). *Corrected the user's "encrypt + decrypt-to-match" framing — passwords
    are hashed and compared, never decrypted.*
  - **Order identity.** `orders.order_number` → `INTEGER GENERATED ALWAYS AS IDENTITY`
    + **UNIQUE** (DB-assigned, rejects client values) for the "one unique order number" promise.
  - **Vector search made functional.** `products` gained `name VARCHAR(255) NOT NULL`,
    `description TEXT` nullable, explicit `embedding VECTOR(384)`; payload template
    `"Product: {name}. Description: {description}"`; pinned model **`bge-small-en-v1.5`**;
    **HNSW** index w/ `vector_cosine_ops`; seq-scans banned (mirrored into §5).
  - **Geo.** `vendors.location` → `GEOGRAPHY(Point, 4326)` (WGS84; native-meter `ST_DWithin`).
  - **`products.category_id`** FK → `categories.id` made explicit with ON DELETE RESTRICT.
  - **Scope boundary.** Scenario 2 rewritten: application transactional orchestration
    (`SELECT … FOR UPDATE`, session mgmt, execution ordering) **stripped** and declared
    out of scope (owned by a later checkout feature); only schema-level guarantees remain.
  - **Governance honesty.** Un-checked the false DoD box "No unresolved [NEEDS
    CLARIFICATION]" — `plan.md` is still all placeholders, so claiming completeness is an
    anti-pattern (P2).

- **`[NEEDS CLARIFICATION]` resolved:** price/currency, cart & order quantities, frozen
  snapshot, nullable-vs-RESTRICT (#8), sync/async driver, category ENUM, cascade rules,
  receipt timestamp, `stock_quantity`, auth model + credential storage, `order_number`
  identity/uniqueness, embedding source/model/index, GEOGRAPHY SRID, checkout scope.

- **Still open (blocking DoD):**
  - `plan.md` is entirely `[NEEDS CLARIFICATION]` → P1 dry-run gate unmet; no
    implementation may begin.
  - §2 Functional Requirements table is malformed (FR-1 non-decision rationale; FR-2/FR-3
    empty cells; blank lines break the table).
  - `vendors`↔owning-`user` relationship still undefined (vendors can't authenticate / be
    tied to an account).

- **Tooling:** Authored `.claude/skills/review-spec/SKILL.md` — a read-only, adversarial
  spec auditor (severity-ranked blockers/ambiguities/forks/edge-cases). Realizes the
  `spec-validate` skill candidate tracked in `CLAUDE.local.md`. Re-ran it on this feature.

- **Files altered:** `specs/001-db-schema/spec.md`, `SPEC.md` (auth row),
  `.claude/skills/review-spec/SKILL.md` (new).

---

## 2026-06-21 — Session 3: review-spec run 2 + follow-up fixes

- **Context / goal:** Re-run `review-spec` on the hardened spec; address findings.
- **Findings (run 2):** `plan.md` now drafted (4 milestones) but still AWAITING APPROVAL
  (P1 gate). Open schema gaps surfaced: `carts` timestamp columns referenced by the §3
  criterion but undeclared in §4; `products.embedding` nullability unspecified; no
  `UNIQUE (vendor_id, product_id)` on `inventory`; `vendors` has no owning-user/identity.
  Stale §2 FR table and stale DoD comment remain.
- **Decisions made:** Declared `carts.created_at` (write-once) and `carts.updated_at`
  (`server_default=now()` + `onupdate=now()`) as explicit columns; aligned the §3
  "Automated Timestamps (carts)" criterion. Resolves review-run-2 blocker #2.
- **Still open:** plan approval (P1); `products.embedding` nullability; `inventory`
  uniqueness; `vendors`↔user link; malformed §2 FR table; stale DoD line-170 comment;
  `plan.md` unclosed ```sql fence.
- **Files altered:** `specs/001-db-schema/spec.md`.
