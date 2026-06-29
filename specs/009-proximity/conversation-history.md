# Conversation History — Feature 009: Proximity

Append-only, cumulative log of every working session on this feature
(Constitution P3 & P7). Earlier entries are NEVER overwritten or truncated.
Each entry: context/goal · decisions + reasoning · edge cases / unknowns ·
`[NEEDS CLARIFICATION]` raised or resolved · files altered.

---

## 2026-06-24 — Session 1: Feature scaffolding

- **Context / goal:** Initialise feature `009-proximity` via `/spec-create`.
- **Decisions:** Created `specs/009-proximity/` with `spec.md`, `plan.md`, `prompts.md`,
  `conversation-history.md`; set `.active_feature` → `009-proximity` (P7).
- **Unknowns raised:** spec.md & plan.md seeded with `[NEEDS CLARIFICATION]` markers
  to be resolved with the user before any implementation (P1, P2).
- **Files altered:** new feature folder + `.active_feature`.

## 2026-06-24 — Session 2: Spec + plan filled (forks resolved)

- **Context / goal:** Turn the scaffold into a complete, unambiguous contract for
  vendor location capture → PostGIS persistence → 5 km proximity query.
- **Codebase findings:** No MCP usage exists in the backend (`mcp` is a
  declared-but-unused dep). Two divergent vendor models: the **wired** one
  (`models/vendor.py`) stores `shop_location_lat/lon` as `Float`; the **unreached**
  target (`models/models.py`) uses PostGIS `Geography(POINT,4326)` + GiST. Existing
  `POST /api/auth/register-vendor` already accepts `location:{lat,lon}`.
- **Decisions (from user Q&A, P2 — no guesses):**
  - **MCP = Supabase MCP server** (`mcp.supabase.com`, project_ref
    `hstezspiljhcuhjraitb`), registered at project scope via `claude mcp add`;
    used as the DDL/persistence control plane. Runtime app still uses `DATABASE_URL`.
  - **Location source = browser Geolocation API** (no geocoding API/secret).
  - **Persistence = `geography(Point,4326)` on Postgres, Float fallback on SQLite**
    (dialect-keyed), additive nullable column + GiST index, backfilled.
  - **Scope = persist + 5 km radius query** (`GET /api/vendors/nearby`,
    `PROXIMITY_RADIUS_KM=5.0`, configurable). Price ranking stays in 006/008.
- **Edge cases captured:** geolocation denied → fail-closed onboarding; out-of-range
  coords → 400; location-less/inactive vendors excluded from nearby; `radius_km ≤ 0`
  → 400; empty result is 200.
- **Risks logged in plan:** R1 shared 003-owned `vendors` model (additive only);
  R2 frontend geolocation is 004-owned (coordinated edit); R3 no PostGIS in SQLite
  (Haversine fallback); R4 extension-before-column migration ordering; R5 secrets in
  `.env` only (P4).
- **Unknowns resolved:** all four scaffolded `[NEEDS CLARIFICATION]` markers closed;
  none remain. **Status:** plan.md AWAITING APPROVAL (P1) — no implementation yet.
- **Files altered:** `spec.md`, `plan.md`, `prompts.md`, `conversation-history.md`.
