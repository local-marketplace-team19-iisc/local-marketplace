# Prompts — Feature 007: Deployment

Chronological log of LLM prompts for this feature (Constitution P3).

## Chronological log

1. **"/spec-create 007-deployment"** — scaffolded the feature folder and audit artifacts.
2. **"create-spec '007-deployment' where a Vercel app deployment for a full stack application with a FastAPI powering the backend and React powering the frontend. We need a requirements.txt file to be created. For Postgres DB, use MCP as a tool to connect to claude mcp add --scope project --transport http supabase ... MCP implementation must use the HTTP/SSE (Server-Sent Events) transport mechanism, and DB calls to execute within Vercel's strict serverless timeout limits for free tier."** — filled spec.md and plan.md with full deployment architecture; no `[NEEDS CLARIFICATION]` markers remain.

## Recurring interactions

Repeated prompts (verbatim or by intent), ranked by frequency. Any interaction
recurring **≥3 times** is flagged `[SKILL CANDIDATE]` for promotion into a reusable
skill (Constitution P3).

| Count | Interaction (by intent) | Source prompts | Flag |
| :-- | :-- | :-- | :-- |
| 1 | Scaffold a new feature spec | #1 | — |
| 1 | Fill deployment spec (Vercel + Supabase MCP) | #2 | — |
