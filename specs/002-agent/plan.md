# Plan — Feature 002: Conversational Agent (Dry-Run)


## Scope

The agent is the customer and vendor-facing brain that turns natural-language input (text,
voice transcribed via Whisper, image-text via Tesseract) into validated
tool calls against a deterministic in-memory catalog. The LLM does
understanding pricing, inventory, and confirmation gating stay
deterministic in code.


### In scope (this PR ships exactly these) : 

1. **Python package** at `backend/agent/` (29 source files: `cli.py`,
   `orchestrator.py`, `planner.py`, `memory.py`, `schemas.py`,
   `tools/*.py`, `io/{asr,ocr,cli}.py`, `prompts/*.txt`, `utils/config.py`,
   `config/agent.yaml`). Imports use `backend.agent.*`.
2. **Test suite** at `backend/agent/tests/` (8 modules + 2 binary
   fixtures). `make agent-test` must report `66 passed, 2 skipped, 2
   deselected` (the 2 deselected are `@pytest.mark.slow` real-fixture
   tests, opt-in via `pytest -m slow`.
3. **Spec artifacts** at `specs/002-agent/`: `agent-spec.md` (feature
   contract), `plan.md` (this file), `prompts.md` (chronological log +
   recurring-interactions ranking), `conversation-history.md` (append-only
   per-session log). Layout mirrors `specs/000-app-scaffold/` exactly,
   with the feature-002 contract named `agent-spec.md` (rather than the
   generic `spec.md`) so a reader scanning across feature folders
   immediately sees which one is the agent contract.
4. **Append-only edits** to five existing files:
   - `pyproject.toml` — new `[agent]` optional extra; `pytest-asyncio`
     in `[dev]`; `pytest` markers and `testpaths`; `ruff.exclude`.
   - `Makefile` — `agent`, `agent-vendor`, `agent-customer`,
     `agent-test`, `agent-lint` targets. Existing targets untouched.
   - `.env.example` — placeholder block for `OPENAI_API_KEY` and the
     `CIRCUIT_*` knobs (Constitution P4 — placeholders only).
   - `.gitignore` — `models/`, `traces/`.
   - `README.md` — new "Run (agent — feature 002)" section.
5. **One helper script** at `scripts/download_whisper_base_en.sh`
   (executable; documented in the README for offline ASR setup).

### Out of scope (deferred, each is a future feature with its own spec)

The items below are SPEC §5 `later` rows. Touching any of them in this PR
is a blocking defect:

- **HTTP exposure of the agent** (e.g. `POST /agent/turn` on the FastAPI
  app from feature 000). The agent is CLI-only this round.
- **Durable storage.** No SQL, no migrations, no pgvector. The
  in-memory `tools/_store.py` remains the catalog.
- **Search index.** No embeddings, no Qdrant, no reranker. Customer
  search uses the keyword + price + Haversine path already in
  `customer_tools.py`.
- **Authentication / registered users.** No login surface; the REPL
  uses an anonymous `dev_<role>` user id.
- **React frontend** under `frontend/`.
- **Docker / deploy stack** for the agent (the existing feature-000
  Dockerfile/compose are untouched but no new images are added).
- **Multilingual prompts.** English-only this round; `llm.ocr.lang` and
  `llm.asr.language_hint` are configurable for future enabling.

## Acceptance criteria being targeted

1. `python -m backend.agent.cli --role vendor` starts a REPL, prints which LLM
    client was selected (`CircuitClient` / `OpenAIClient` / `StubLLMClient`), and
    accepts text input ending in a confirmed `add_product`.
2. `python -m backend.agent.cli --role customer` starts a REPL and routes a
    free-text query to `search_products`, rendering up to 3 ranked rows.
3. Voice path: `/voice <path>.wav` transcribes via Whisper (offline if
    `models/faster-whisper-base.en` present) and feeds the text to the planner.
4. Image path: `/image <path>.jpg` runs Tesseract OCR and feeds the recognised
    text to the planner.
5. `pytest backend/agent` is green (the 64 tests + 2 expected skips we already
    have in `DL_Project/tests/`).
6. `ruff check .` is clean across the merged code (no new lint debt at scaffold
    quality).
7. `make agent` and `make agent-test` work as documented in the README.
8. **No regression of feature 000.** `make run`, `make test`, `make lint` still
    pass exactly as today.

## Files to CREATE

### Agent runtime (Python package)

| `backend/agent/__init__.py` | package marker |
| `backend/agent/cli.py` | interactive REPL (`python -m backend.agent.cli --role …`) |
| `backend/agent/orchestrator.py` | turn loop: planner → validate → execute, with confirmation gating |
| `backend/agent/planner.py` | LLM-agnostic planner; `OpenAIClient`, `CircuitClient`, `StubLLMClient`; safe-parse |
| `backend/agent/memory.py` | `SessionStore` protocol; `InMemoryStore` (default), `RedisStore` (with startup ping fallback) |
| `backend/agent/schemas.py` | Pydantic models: `Session`, `Turn`, `PlannerOutput`, `ToolCall`, `PendingAction`, etc. |
| `backend/agent/io/__init__.py` | package marker |
| `backend/agent/io/asr.py` | `faster-whisper` wrapper; offline model path support |
| `backend/agent/io/ocr.py` | `pytesseract` wrapper; PIL preprocessing |
| `backend/agent/io/input-spec.md` | I/O modality specification (already authored in DL_Project) |
| `backend/agent/prompts/__init__.py` | `load("system_vendor.txt")` helper |
| `backend/agent/prompts/system_vendor.txt` | vendor system prompt (worked-example version we just fixed) |
| `backend/agent/prompts/system_customer.txt` | customer system prompt |
| `backend/agent/prompts/system_router.txt` | role-router system prompt |
| `backend/agent/tools/__init__.py` | tool `REGISTRY`; imports the baseline tool modules |
| `backend/agent/tools/base.py` | `@tool` decorator, `Tool` dataclass, `ToolContext`, `tool_schemas_for_prompt` |
| `backend/agent/tools/_store.py` | in-memory product/store dicts + ID counters |
| `backend/agent/tools/vendor_tools.py` | `add_product`, `get_my_catalog` (confirmation-gated) |
| `backend/agent/tools/customer_tools.py` | `search_products`, `get_store` |
| `backend/agent/tools/nlp_tools.py` | `extract_product_fields`, `is_affirmative`, `is_negative` |
| `backend/agent/config/agent.yaml` | runtime config; `session.store=inmem` by default |
| `backend/agent/config/__init__.py` | `load_cfg()` (uses `utils.config`-style YAML loader) |
| `backend/agent/utils/__init__.py` | package marker |
| `backend/agent/utils/config.py` | YAML → dotted-attribute config loader |

### Tests (scoped to the agent feature)

| `backend/agent/tests/__init__.py` | package marker |
| `backend/agent/tests/conftest.py` | fixtures shared by agent tests |
| `backend/agent/tests/test_schemas.py` | Pydantic model contracts |
| `backend/agent/tests/test_io_asr.py` | mocked Whisper path tests |
| `backend/agent/tests/test_io_ocr.py` | mocked Tesseract tests |
| `backend/agent/tests/test_tools_vendor.py` | `add_product`, `get_my_catalog`, NLP helpers |
| `backend/agent/tests/test_tools_customer.py` | `search_products`, `get_store` |
| `backend/agent/tests/test_orchestrator.py` | end-to-end turn loop with a ScriptedLLMClient |
| `backend/agent/tests/test_planner_circuit.py` | CircuitClient wire-format lock-down (offline httpx stub) |
| `backend/agent/tests/fixtures/sample_voice.wav` | known-good ASR fixture (copied from DL_Project) |
| `backend/agent/tests/fixtures/sample_image.jpg` | known-good OCR fixture (copied from DL_Project) |
| `backend/agent/tests/fixtures/README.md` | how the fixtures were generated |

### Helper scripts

| `scripts/download_whisper_base_en.sh` | pre-download `base.en` weights for offline ASR |

### Spec artifacts (Constitution P3 — already partially present)

| `specs/002-agent/agent-spec.md` | architectural contract for this feature |
| `specs/002-agent/prompts.md` | chronological prompt log + recurring-interactions ranking |
| `specs/002-agent/conversation-history.md` | append-only, multi-session history |
| `specs/002-agent/plan.md` | **this file** |

## Files to MODIFY (append/merge only — Constitution P6)

| `pyproject.toml` | append agent runtime deps (`httpx`, `pydantic`, `pyyaml`, `python-dotenv`, `faster-whisper`, `pillow`, `pytesseract`, `redis`, `eval_type_backport`) under a new `agent` optional-extra. Add `pytest-asyncio` to `dev`. Extend `tool.pytest.ini_options.testpaths` to include `backend/agent/tests`. |
| `.env.example` | append placeholder rows for `OPENAI_API_KEY`, `CIRCUIT_*`, `CIRCUIT_VERIFY_SSL` (placeholders only — P4). |
| `.gitignore` | append `models/`, `traces/`, `**/__pycache__/` (idempotent — keep existing rules). |
| `README.md` | append "## Run (agent — feature 002)" section: install with `pip install -e ".[dev,agent]"`, `make agent`, `make agent-test`, env-var notes. |
| `Makefile` | append `agent`, `agent-test`, `agent-lint` targets. Existing targets untouched. |

## Key execution decisions (resolving feature-level unknowns)

1. **Import path rewrite.** All `from agent.X` / `import agent.X` references in
   the DL_Project source become `from backend.agent.X`. The rewrite is mechanical
   (`grep -rn "from agent" DL_Project` → 27 matches; each one renamed). We do
   not introduce a shim package; the rename is the source of truth.

2. **Session store default = `inmem`.** Already the upstream default after the
   fix in this conversation. Redis remains supported and ping-probes at startup
   (`build_store`) so misconfig surfaces immediately, never mid-turn.

3. **LLM client selection precedence** (preserved from DL_Project):
   `CircuitClient` (if all `CIRCUIT_*` env vars are set) → `OpenAIClient` (if
   `OPENAI_API_KEY`) → `StubLLMClient`. Selection is printed to stderr on REPL
   startup so the grader sees which backend ran.

4. **Circuit wire format** matches the working reference at
   `xrSanity2_Project/DDTSMgmt_Backend/llm_description_Genration/
   Headline-Desc_CircuitApi.py`: Basic-auth token endpoint,
   `/openai/deployments/{model}/chat/completions`, `api-key` header,
   `app-key` carried inside `body.user`. Locked down by
   `test_planner_circuit.py` (11 tests).

5. **ASR offline path.** `config/agent.yaml` keeps the `model_path:
   models/faster-whisper-base.en` line; `models/` is gitignored. The download
   script is committed so a grader can repro: `bash scripts/download_whisper_base_en.sh`.

6. **No FastAPI mount.** Per Constitution P6 (file idempotency) we don't touch
   `backend/app/main.py`. The agent is reachable via `python -m backend.agent.cli`
   only. A `/agent/turn` HTTP route is a future feature with its own spec.

7. **`.env` handling.** `python-dotenv` loads `.env` in `planner.py` exactly as
   today. The committed `.env.example` carries placeholders only (Constitution
   P4). The real `.env` stays gitignored.

8. **Test-runner coverage.** `tool.pytest.ini_options.testpaths` grows to
   `["backend/tests", "backend/agent/tests"]`. The single `make test` target
   still runs everything (000 + 002); we additionally expose `make agent-test`
   for a faster scoped loop. `pytest-asyncio` is added to `dev` (required by
   the orchestrator tests).

## Pinned dependencies appended to pyproject.toml

Under a new optional-extra `agent`:

- `httpx==0.28.1` *(already pinned for dev; re-stated here for runtime)*
- `pydantic==2.10.4`
- `pyyaml==6.0.2`
- `python-dotenv==1.0.1`
- `faster-whisper==1.0.3`
- `pillow==11.0.0`
- `pytesseract==0.3.13`
- `redis==5.2.1`
- `eval_type_backport==0.2.0`  *(needed by Pydantic on Py 3.11 for `X | Y` annotations)*

Under `dev`:

- `pytest-asyncio==0.24.0` (newly required)

System dependencies (out of pip's reach, documented in README):

- `ffmpeg` (Whisper audio decode)
- `tesseract` (OCR engine)

## Architectural risks

- **R1 — In-memory store is per-process.** A REPL restart loses sessions and
  the product catalog. Acceptable; the SPEC §4 layout flags durable storage
  (`backend/app/models/`, `backend/migrations/`) as `later`, owned by a future
  DB feature.
- **R2 — Circuit access requires Cisco network.** Off-network graders fall back
  to `OpenAIClient` (via `OPENAI_API_KEY`) or `StubLLMClient`. README explains
  the precedence and how to demonstrate each path.
- **R3 — Whisper / Tesseract heavy install.** Both pull large native deps.
  We mark them under the `agent` optional extra so feature 000's
  install path (`pip install -e ".[dev]"`) stays light. Mitigation: README
  documents `pip install -e ".[dev,agent]"` for full feature.
- **R4 — Prompt drift on long sessions.** Mitigated by rewriting past assistant
  turns into the JSON envelope shape (done upstream in this conversation) and
  by the rolling `session.max_turns_in_context` window.
- **R5 — No HTTP surface.** Graders who only test via curl will not see the
  agent. README and the spec call this out explicitly; the `/agent/turn` route
  is a clean future-feature.

## Verification steps (post-implementation, Phase VALIDATE)

1. `pip install -e ".[dev,agent]"` — succeeds.
2. `make test` — full suite green (feature 000 health tests + feature 002 agent
   tests). Expected: `66 passed, 2 skipped`.
3. `make lint` — clean.
4. `make run` — `/health` still serves `200 {"status":"OK"}` (no regression).
5. `make agent` with `--role vendor`:
   ```
   you> add 10 kg masuri rice 58/kg
   bot> Listing: masuri rice — 10 kg @ ₹58. Reply "yes" to add or "no" to cancel.
   you> yes
   bot> Listed ✅  masuri rice (10 kg) @ ₹58 — product id: prod_<8>
   you> /catalog
   1. masuri rice — 10 kg — ₹58 — id:prod_<8>
   ```
6. `make agent` with `--role customer`:
   ```
   you> any rice near me?
   bot> 1. … — masuri rice — ₹58 — 0 km
   ```
7. ASR smoke: `/voice backend/agent/tests/fixtures/sample_voice.wav` →
   transcribed text fed to planner.
8. OCR smoke: `/image backend/agent/tests/fixtures/sample_image.jpg` →
   recognised text fed to planner.

## Rollback plan

The agent code lives entirely under `backend/agent/`. To revert: delete that
directory, drop the `[agent]` extra from `pyproject.toml`, remove the agent
targets from the Makefile, and remove `specs/002-agent/` (leaving the audit
trail in Git history). Feature 000 is untouched and continues to serve `/health`.
