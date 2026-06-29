# Prompts — Feature 009: Proximity

Chronological log of LLM prompts for this feature (Constitution P3).

## Chronological log

1. **"/spec-create 009-proximity"** — scaffolded the feature folder and audit artifacts.
2. **"spec-create '009-proximity' where during vendor onboarding, vendors will provide
   their location (lat/long) using some location API and we then need to persist the
   vendors location in postgres using postgis. Make sure we are persisting the vendors
   in postgres db using mcp protocol."** — feature intent; drove the four clarifying
   forks below.
3. **(clarifying Q&A, AskUserQuestion)** — resolved: MCP = Supabase MCP server
   (`project_ref hstezspiljhcuhjraitb`); location source = browser Geolocation API;
   persistence = PostGIS `geography(Point,4326)` with Float SQLite fallback; scope =
   persist **and** the 5 km radius query. spec.md + plan.md filled accordingly.

## Recurring interactions

Repeated prompts (verbatim or by intent), ranked by frequency. Any interaction
recurring **≥3 times** is flagged `[SKILL CANDIDATE]` for promotion into a reusable
skill (Constitution P3).

| Count | Interaction (by intent) | Source prompts | Flag |
| :-- | :-- | :-- | :-- |
| 1 | Scaffold a new feature spec | #1 | — |
