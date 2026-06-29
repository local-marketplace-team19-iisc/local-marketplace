# Plan — Feature 009: Proximity (Dry-Run)

> **Iron-Clad Rule (Constitution P1 / SPEC §8):** this dry-run MUST be reviewed and
> **approved by the user** before any implementation file is created or modified.

## Scope

**In scope**

- Capture vendor lat/long from the browser Geolocation API at onboarding and
  persist it in Postgres as `geography(Point, 4326)` (Float fallback on SQLite).
- Enable PostGIS + add the `location` column + GiST index on the Supabase
  database **through the Supabase MCP server**.
- A proximity radius query `GET /api/vendors/nearby` (default 5 km, configurable)
  returning active in-range vendors nearest-first with distance.

**Out of scope**

- Cheapest-first product/price ranking and cart/order composition (006/008/007).
- Geocoding from a postal address; map UI; accuracy refinement.
- Reverse-geocoding / display of human-readable addresses.

## Pre-flight (tooling, before code) — requires approval

| Step | Command / action | Notes |
| :-- | :-- | :-- |
| Register MCP | `claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp?project_ref=hstezspiljhcuhjraitb"` | Writes project-scoped MCP config (e.g. `.mcp.json`). Tooling config, **not** a feature implementation file. I will not run this until you approve. |
| Verify reach | List tables / run `SELECT postgis_version()` via the Supabase MCP server | Confirms connectivity + extension availability before DDL. |

## Files to CREATE

| Path | Purpose |
| :-- | :-- |
| `backend/app/api/routes/vendors.py` | `GET /api/vendors/nearby` proximity endpoint (+ optional `PUT /api/vendors/me/location` to re-capture). |
| `backend/app/services/proximity_service.py` | Dialect-keyed query: PostGIS `ST_DWithin`/`ST_Distance` on Postgres, Haversine on SQLite. |
| `backend/app/schemas/proximity.py` | Request/response models (`NearbyVendor`, `distance_km`). |
| `backend/migrations/versions/0005_vendor_geography.py` | Alembic: `CREATE EXTENSION postgis`, add `location geography(Point,4326)`, GiST index, backfill from Float lat/lon. (Applied to Supabase via the MCP server.) |
| `backend/tests/test_proximity.py` | Radius math + edge cases on both PostGIS and SQLite paths. |

## Files to MODIFY (append/merge only — Constitution P6)

| Path | Change |
| :-- | :-- |
| `backend/app/models/vendor.py` | **Additive**: add nullable `location` `geography(Point,4326)` column + GiST index (Postgres dialect). Shared 003-owned model — see R1. |
| `backend/app/services/auth_service.py` | On `register_vendor`, also write the `geography` value (Postgres) alongside the existing Float lat/lon. |
| `backend/app/core/config.py` | Add `PROXIMITY_RADIUS_KM: float = 5.0`. |
| `backend/app/main.py` | `include_router` for the new `vendors` router under `/api/vendors`. |
| `frontend/src/...` (vendor onboarding) | Wire `navigator.geolocation` to populate `location:{lat,lon}` before submit. **004-owned** — see R2; coordinate before touching. |

## Files explicitly NOT touched

- `CLAUDE.md` — human-owned; AI forbidden to modify (Constitution P5).
- `specs/constitution.md`, `SPEC.md` — governing docs; not changed by execution.
- Any file owned by another feature beyond the additive, coordinated changes
  named above (Constitution P6).

## Key execution decisions

1. **PostGIS + Float dual-store, dialect-keyed.** `geography(Point,4326)` is the
   source of truth on Postgres; Float lat/lon is the SQLite-dev fallback and a
   human-readable mirror. Persistence and the nearby query branch on the engine
   dialect (same pattern as the existing `_on_vercel` / sync-vs-async split).
2. **DDL via the Supabase MCP server.** The migration's extension/column/index
   steps are applied to Supabase through the registered MCP server; the runtime
   app keeps connecting over `DATABASE_URL`. MCP is the control plane, not a
   runtime dependency on the request path.
3. **Distance in metres, surfaced as km.** `ST_Distance(geography, geography)`
   returns metres; the API returns `distance_km`. SQLite path uses a Haversine
   expression (Earth radius 6371 km).
4. **Radius precedence:** request `radius_km` → else `settings.PROXIMITY_RADIUS_KM`
   (5.0). Validated `> 0`.
5. **Fail-closed onboarding:** no vendor row is written without a valid coordinate.

## Architectural risks

- **R1 — Shared `vendors` model is 003-owned (P6).** 009 must extend it. Mitigation:
  change is strictly **additive** (nullable column + index, backfilled); no
  existing column/semantics altered. Flag for the 003 owner in review.
- **R2 — Frontend geolocation lives in 004 (P6).** The capture call is a 004-owned
  change. Mitigation: 009 fixes the backend contract (unchanged `register-vendor`
  payload shape); the frontend wiring is a small coordinated edit, called out
  explicitly rather than absorbed silently.
- **R3 — PostGIS absent in local SQLite.** Mitigated by the dialect-keyed
  Haversine fallback; proximity is tested on both paths so behaviour can't
  silently diverge.
- **R4 — Migration not yet run on prod path.** Earlier features bootstrap tables
  via `create_all` on SQLite; Postgres uses Alembic. The geography column needs
  the `postgis` extension present first — ordering enforced in `0005`.
- **R5 — Secret handling (P4).** Supabase DB password / service-role key must
  reside only in `.env`; never commit them or embed in the MCP URL beyond the
  non-secret `project_ref`.

## Verification steps (post-implementation)

1. Via the Supabase MCP server: `SELECT postgis_version();` succeeds; `vendors`
   has a `location` column and `ix_vendors_location_gist`.
2. Register a vendor with `{lat, lon}`; confirm non-NULL `location` (Postgres)
   and Float mirror.
3. `GET /api/vendors/nearby?lat=..&lon=..` → in-range vendors nearest-first with
   `distance_km`; out-of-range/inactive/location-less excluded; empty list when
   none in range.
4. `radius_km` override works; `radius_km ≤ 0` → `400`.
5. `make test` green (both PostGIS + SQLite proximity paths), `make lint` clean.
6. `docs/architecture.md` gains the 009 decisions (PostGIS geography, MCP control
   plane, dual-store fallback).

---
**STATUS: AWAITING APPROVAL.** No implementation file will be created or modified
until this plan is approved by the user.
