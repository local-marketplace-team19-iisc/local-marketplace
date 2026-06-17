# Constitution — Local Marketplace

This constitution defines the non-negotiable governance principles for the Local Marketplace Chatbot Application. Every specification, design decision, implementation, and code review MUST comply with these principles. They are ordered by priority — when principles conflict, higher-ranked principles prevail.


Principle 1 - Dry-Run before execution

Every feature must have a reviewed and approved `plan.md` in its spec directory before any implementation file is created or modified.

Principle 2 — Executable, unambiguous specs

Specs are precise, complete, unambiguous. Unknowns are [NEEDS CLARIFICATION], never guesses. Approved specs to be ensured that it carries no unresolved markers.

Principle 3 - Audit trail

Every feature directory must maintain `spec.md`, `prompts.md`, and `conversation-history.md` . Omission is a blocking defect.

Principle 4 - No credentials in source.

Secrets live in `.env` (gitignored). `.env.example` is committed with placeholder values only.

Principle 5 - AI assistant context

`CLAUDE.md` (repo root) - This file provides guidance to Claude Code when working with code in this repository. Contains: stack, run/test/lint commands, how to handle errors, directory layout, git workflow. Gitignored by default so each developer keeps a local copy; commit it if the team wants shared AI context. Feature-specific context belongs in `specs/NNN-slug/spec.md`, not here.

Principle 6 - File idempotency

When any spec or scaffold is executed, the agent must check for file existence before writing:
- Governance & config files (`constitution.md`, `.gitignore`, `pyproject.toml`, `CLAUDE.md`, etc.) — if the file exists, append or merge only missing sections. Never truncate or overwrite existing content.
- Feature code files — only create or modify files scoped to the current feature. Files owned by another feature are off-limits.