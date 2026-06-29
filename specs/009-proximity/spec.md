---
title: Feature 009: Proximity
feature: 009-proximity
status: draft
created: 2026-06-24
---

# Feature 009: Proximity — Specification

> Architectural contract for feature `009-proximity` (Constitution P3).
> Mark every unknown `[NEEDS CLARIFICATION: ...]` — never guess (Constitution P2).
> Outranked by `specs/constitution.md` and the master `SPEC.md`.

## 0. Summary

Capture a vendor's geographic location (lat/long) during onboarding via the
browser **Geolocation API**, **persist it in PostgreSQL/PostGIS** as a
`geography(Point, 4326)` value, and expose a **proximity radius query**
(default 5 km, configurable) that returns the vendors within range of a
customer's location, nearest-first. The schema change and persistence against
the Supabase-hosted Postgres are driven through the **Supabase MCP server**
(`mcp.supabase.com`, project_ref `hstezspiljhcuhjraitb`) registered at project
scope; the runtime app reaches the same database over `DATABASE_URL`.

This satisfies the SPEC §2 promise of "in-radius listings … by default 5 km
proximity and later configurable" by providing the geo primitive the customer
journey filters on. Product/price ranking (cheapest-first, distance tie-break)
stays in the consuming feature (006/008) and is out of scope here.

## 1. User Scenarios & Edge Cases

1. **Scenario — Vendor shares location at onboarding.**
   - *Given* a vendor is registering a shop on the dashboard,
   - *When* the browser's Geolocation API returns `{lat, lon}` and the vendor
     submits registration,
   - *Then* the backend persists the coordinates as a PostGIS
     `geography(Point, 4326)` value on that vendor's row (Float lat/lon retained
     for the SQLite dev fallback), and registration succeeds.
   - **Edge cases:**
     - Browser denies/blocks geolocation → onboarding MUST surface a clear
       "location required" error; the vendor cannot be persisted without a
       valid coordinate (FR-7).
     - Out-of-range coordinates (`lat` ∉ [-90, 90], `lon` ∉ [-180, 180]) →
       rejected `400` before any write (reuses existing validation in
       `register_vendor`).
     - Geolocation returns stale/low-accuracy fix → coordinates still stored
       as given; accuracy refinement is out of scope.

2. **Scenario — Vendor updates a previously stored location.**
   - *Given* an authenticated vendor whose location is already persisted,
   - *When* they re-capture and submit a new `{lat, lon}`,
   - *Then* the `geography` value (and Float fallback) are updated atomically
     and `updated_at` is bumped.
   - **Edge cases:** concurrent update → last write wins (single-row update, no
     cross-row invariant).

3. **Scenario — Customer queries nearby vendors.**
   - *Given* a customer location `{lat, lon}` and an optional `radius_km`,
   - *When* the proximity query runs,
   - *Then* it returns active vendors whose stored location is within
     `radius_km` (default `PROXIMITY_RADIUS_KM = 5`) of the customer, each with
     its great-circle distance, ordered nearest-first.
   - **Edge cases:**
     - No vendor in range → empty list, `200` (not an error).
     - A vendor with no stored location → excluded from results (NULL geography).
     - `radius_km` ≤ 0 or non-numeric → `400`.
     - Vendor `is_active = false` → excluded.

## 2. Functional Requirements & Decisions

| ID | Requirement (MUST/SHOULD) | Decision taken & rationale |
| :-- | :-- | :-- |
| FR-1 | The system MUST capture vendor location as `{lat, lon}` from the browser **Geolocation API** during onboarding. | Frontend (004) reads `navigator.geolocation.getCurrentPosition()` and sends `location: {lat, lon}` to the existing `POST /api/auth/register-vendor` contract — no new external geocoding API, no API key/secret. |
| FR-2 | Vendor location MUST be persisted in Postgres as `geography(Point, 4326)`. | PostGIS is the SPEC §5 mandated proximity store. SRID 4326 (WGS-84) matches lat/long input and the target schema in `backend/app/models/models.py`. |
| FR-3 | On SQLite local dev (no PostGIS) the system MUST fall back to the existing `shop_location_lat` / `shop_location_lon` Float columns. | Local dev loop runs SQLite (CLAUDE.local.md). Dialect-keyed persistence: write geography on Postgres, Floats on SQLite. Floats are also retained on Postgres as a human-readable mirror. |
| FR-4 | The schema change (enable `postgis`, add `location` column, GiST index) and vendor persistence against Supabase Postgres MUST be performed via the **Supabase MCP server**. | User decision. Register once: `claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp?project_ref=hstezspiljhcuhjraitb"`. The MCP server is the dev/agent control plane for DDL + verification; the runtime app still connects over `DATABASE_URL`. |
| FR-5 | The system MUST expose a proximity query returning active vendors within a radius of a given point, nearest-first, each with distance. | `GET /api/vendors/nearby?lat=&lon=&radius_km=`. Postgres: `ST_DWithin(location, point, radius_m)` filter + `ST_Distance` (geography → metres) ordering. SQLite: Haversine SQL expression over the Float columns. |
| FR-6 | The proximity radius MUST default to 5 km and be configurable. | Add `PROXIMITY_RADIUS_KM: float = 5.0` to `Settings`. Query `radius_km` param overrides per-request; absent → setting default. Mirrors SPEC §2 "default 5km … later configurable". |
| FR-7 | Onboarding MUST reject a vendor with missing/invalid coordinates before any write. | Reuse existing `register_vendor` coordinate validation (`lat ±90`, `lon ±180`); add an explicit "location required" path when the Geolocation payload is absent. No partial vendor rows. |
| FR-8 | The proximity query MUST return only the geo primitive (vendor id, shop_name, distance). It MUST NOT rank by price. | Keeps 009 single-purpose. Cheapest-first product ranking + distance tie-break stays in the consuming feature (006/008), composing on top of this filter. |
| FR-9 | Secrets backing the Supabase connection (DB password, service-role key) MUST stay in `.env` (gitignored); only the project_ref / `.env.example` placeholders are committed. | Constitution P4. project_ref is a non-secret identifier; the connection password/keys are not. |

## 3. Success Criteria / Acceptance Criteria

- [ ] A vendor registered with a `{lat, lon}` payload has a non-NULL
      `geography(Point,4326)` value on Postgres (verified through the Supabase
      MCP server) and Float lat/lon on SQLite.
- [ ] `GET /api/vendors/nearby?lat=..&lon=..` returns vendors within the
      default 5 km, nearest-first, each with a `distance_km`, and excludes
      out-of-range, inactive, and location-less vendors.
- [ ] Passing `radius_km` overrides the default; `radius_km ≤ 0` → `400`.
- [ ] Onboarding without a usable geolocation fix fails closed (no vendor row).
- [ ] The `postgis` extension, `location` column, and GiST index exist on the
      Supabase database, applied via the Supabase MCP server.
- [ ] `make test` green and `make lint` clean; proximity math covered by tests
      on both the PostGIS and SQLite-Haversine paths.

## 4. DB Schema Entities

| Entity | Key fields (type) | Relationships | Notes (indexes / constraints) |
| :-- | :-- | :-- | :-- |
| `vendors` (extended) | `location geography(Point, 4326)` NULLABLE (Postgres); existing `shop_location_lat`/`shop_location_lon` `Float` retained (SQLite fallback + mirror) | unchanged — `user_id` → `users.id` (CASCADE) | Add **GiST** index `ix_vendors_location_gist` on `location` (Postgres only). Requires `CREATE EXTENSION IF NOT EXISTS postgis`. Additive, nullable column → backfill existing rows from Float lat/lon. |

> Ownership note: the `vendors` table / `Vendor` model
> (`backend/app/models/vendor.py`) is shared with feature 003 (auth). 009's
> change is **additive** (new nullable column + index) — see plan.md R1 for the
> cross-feature coordination risk.

## 5. Requirement Completeness / Definition of Done

This feature is DONE only when **all** hold:

- [ ] No unresolved `[NEEDS CLARIFICATION]` markers remain (Constitution P2).
- [ ] `plan.md` was written and **user-approved** before any implementation (P1).
- [ ] All Functional Requirements (§2) have passing tests.
- [ ] All Success/Acceptance Criteria (§3) are met and verified.
- [ ] DB entities (§4) are migrated (via the Supabase MCP server); schema
      matches the spec.
- [ ] `make test` green and `make lint` clean.
- [ ] Audit trail current: `spec.md`, `plan.md`, `prompts.md`,
      `conversation-history.md` all committed (P3).
- [ ] `docs/architecture.md` updated with any decision this feature introduced.
