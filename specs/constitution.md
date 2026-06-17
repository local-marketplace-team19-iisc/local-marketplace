# Constitution — Local Marketplace

This constitution defines the non-negotiable governance principles for the Local Marketplace Chatbot Application. Every specification, design decision, implementation, and code review MUST comply with these principles. They are ordered by priority — when principles conflict, higher-ranked principles prevail.


Principle 1 - Dry-Run before execution

Every feature must have a reviewed and approved `plan.md` in its spec directory before any implementation file is created or modified.

Principle 2 — Executable, unambiguous specs

Specs are precise, complete, unambiguous. Unknowns are [NEEDS CLARIFICATION], never guesses. Approved specs to be ensured that it carries no unresolved markers.

Principle 3 - Audit trail

Every feature directory must maintain `spec.md`, `prompts.md`, and `conversation-history.md` . Omission is a blocking defect. feature 000 is exempt from spec.md

Principle 4 - No credentials in source.

Secrets live in `.env` (gitignored). `.env.example` is committed with placeholder values only.

Principle 5 - AI assistant context

CLAUDE.md (Shared Context): The team's global AI rulebook (stack, commands, architecture). Human-owned.

Changes must be made by a human via Pull Request.

AI assistants are strictly forbidden from auto-modifying this file.

CLAUDE.local.md (Personal Context): For individual workflows, local quirks, and active task tracking. Ignored by Git. AI may freely write here.

Feature Context (specs/NNN-slug/spec.md): Feature-specific instructions and logic belong in their respective spec files, never crammed into the root CLAUDE.md.

Promoting Rules: If an AI discovers a universally useful workflow locally, a developer should manually PR that rule into the shared CLAUDE.md.

Principle 6 - File idempotency

When any spec or scaffold is executed, the agent must check for file existence before writing:
- Governance & config files (`constitution.md`, `.gitignore`, `pyproject.toml`, `CLAUDE.md`, etc.) — if the file exists, append or merge only missing sections. Never truncate or overwrite existing content.
- Feature code files — only create or modify files scoped to the current feature. Files owned by another feature are off-limits.