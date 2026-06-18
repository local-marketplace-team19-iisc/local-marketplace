# Constitution — Local Marketplace

This constitution defines the non-negotiable governance principles for the Local Marketplace Chatbot Application. Every specification, design decision, implementation, and code review MUST comply with these principles. They are ordered by priority — when principles conflict, higher-ranked principles prevail.


#Principle 1 - Dry-Run before execution

Every feature must have a reviewed and approved `plan.md` in its spec directory before any implementation file is created or modified.

#Principle 2 — Executable, unambiguous specs

Specs are precise, complete, unambiguous. Unknowns are [NEEDS CLARIFICATION], never guesses. Approved specs to be ensured that it carries no unresolved markers.

#Principle 3 - Audit trail

Every feature directory must maintain three artifacts, and all three MUST be committed to version control (Git) — never gitignored, never left as untracked or local-only scratch:

- `spec.md` — the architectural contract. (Feature 000 is exempt: the master `SPEC.md` is its spec.)
- `prompts.md` — a chronological log of the LLM prompts provided. It MUST also surface recurring interactions: in a "Recurring interactions" section, prompts that repeat (verbatim or by intent) are listed with an occurrence count and ranked by frequency (most frequent first). Any interaction recurring **3 or more times** (default threshold) is flagged `[SKILL CANDIDATE]` — a prime candidate to be promoted into a reusable skill. This keeps the log doubling as a ranked backlog of automation opportunities.
- `conversation-history.md` — an append-only, cumulative log of every working session on the feature. Each session entry MUST capture: the session's context/goal, the decisions made and the reasoning behind them, edge cases and unknowns discovered, and any `[NEEDS CLARIFICATION]` raised or resolved. Earlier entries are never overwritten or truncated (consistent with Principle 6), so that when a new session begins, no context, reasoning, or edge-case discovery is ever lost.

Omission of any artifact — or beginning implementation work in a session without first appending that session to `conversation-history.md` — is a blocking defect.

#Principle 4 - No credentials in source.

Secrets live in `.env` (gitignored). `.env.example` is committed with placeholder values only.

#Principle 5 - AI assistant context

- CLAUDE.md (Shared Context): The team's global AI rulebook (stack, commands, architecture). Human-owned. Changes must be made by a human via Pull Request. AI assistants are strictly forbidden from auto-modifying this file.
- CLAUDE.local.md (Personal Context): For individual workflows, local quirks, and active task tracking. Ignored by Git. AI may freely write here.
- Feature Context (specs/NNN-slug/spec.md): Feature-specific instructions and logic belong in their respective spec files, never crammed into the root CLAUDE.md.
- Promoting Rules: If an AI discovers a universally useful workflow locally, a developer should manually PR that rule into the shared CLAUDE.md.

#Principle 6 - File idempotency

When any spec or scaffold is executed, the agent must check for file existence before writing:
- Governance & config files (`constitution.md`, `.gitignore`, `pyproject.toml`, `CLAUDE.md`, etc.) — if the file exists, append or merge only missing sections. Never truncate or overwrite existing content.
- Feature code files — only create or modify files scoped to the current feature. Files owned by another feature are off-limits.

#Principle 7 - Context Binding & Automated Artifact Management via .active_feature

A gitignored `.active_feature` file at the project root holds the single current feature ID (e.g., `001-db-schema`). It is the canonical source of truth for which feature is active, and is never committed (consistent with Principle 4's treatment of local-only state).

- **Context binding.** At the start of every interaction, the agent MUST implicitly read `.active_feature` and bind all subsequent work to the corresponding `specs/<active-feature>/` directory — its `spec.md`, `plan.md`, `prompts.md`, and `conversation-history.md`. The agent does not ask the user which feature is active when this file resolves successfully.
- **Fail-closed.** If `.active_feature` is missing, empty, or names a directory that does not exist under `specs/`, the agent MUST halt execution and ask the user to set a valid active feature. It MUST NOT guess the feature, fall back to a default, or proceed with implementation while context is unbound.
- **Automated history appending.** At the conclusion of any development session, milestone, or major architectural decision, the agent MUST autonomously append a timestamped, concise entry to `specs/<active-feature>/conversation-history.md` — capturing the session's context/goal, the decision(s) made and their reasoning, and the files altered. This is part of the agent's normal output generation, not a step that requires user permission, and it MUST satisfy the append-only guarantees of Principle 3 and Principle 6 (earlier entries are never overwritten or truncated).