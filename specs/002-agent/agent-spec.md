---
title: Feature 002 — Conversational Agent
introduces:
  - SPEC §3 user journeys (text input path, vendor : add-product, customer : search)
  - SPEC §5 "Customer surface (web chatbot — text and voice already wired)"
---

# Feature 002 — Conversational Agent

The agent is the customer and vendor-facing intelligence layer. It turns
natural-language input (text, voice transcribed via Whisper, image-text via
Tesseract) into validated tool calls against a deterministic in-memory
catalog. The LLM does *understanding* pricing, inventory, and confirmation
gating stay deterministic in code.

This feature is **CLI-only** in this iteration. An HTTP route on the FastAPI
app (POST /agent/turn) is intentionally deferred to a future feature so the
core agent shape can be validated end-to-end before being exposed.

## 1. Goals

1. Vendor REPL: python -m backend.agent.cli --role vendor accepts a natural-
   language listing (e.g. "add 10 kg masuri rice 58/kg"), previews the parsed
   draft, and writes to the catalog only after explicit user confirmation.
2. Customer REPL: python -m backend.agent.cli --role customer accepts a free-
   text query, calls search_products, and renders up to 3 ranked rows.
3. Multimodal input parity: voice (/voice <wav>) and image (/image <jpg>)
   produce text that follows the same downstream path as keyboard text.
4. Provider portability: planner runs against OpenAI directly **or** the
   Circuit gateway (egai / Azure-OpenAI passthrough) **or** a deterministic
   stub for offline grading. Selection is driven by env vars, printed on
   startup.
5. Safety invariants: LLM output is Pydantic-validated, tool args are
   re-validated at the tool boundary, mutations (add_product) never run on
   the turn they were proposed.

## 2. Non-goals

- Persistence (SQL, vector index, search ranking via embeddings) — later.
- HTTP exposure of the agent — later feature with its own spec.
- Multilingual prompts (English only this round for text to text , image to text and voice to text. 

## 3. Architecture (this feature only)

```
backend/agent/
├── cli.py                 # REPL entrypoint (text + /voice + /image slash-cmds)
├── orchestrator.py        # turn loop, confirmation gating, RBAC
├── planner.py             # LLM-agnostic, OpenAI / Circuit / Stub clients
├── memory.py              # SessionStore: InMemoryStore (default) or RedisStore
├── schemas.py             # Pydantic: Session, Turn, PlannerOutput, ToolCall, ...
├── prompts/               # system_{vendor,customer}.txt
├── tools/
│   ├── base.py            # @tool decorator + Tool dataclass + REGISTRY
│   ├── _store.py          # in-memory product/store dicts
│   ├── vendor_tools.py    # add_product (confirm-gated), get_my_catalog
│   ├── customer_tools.py  # search_products, get_store
│   └── nlp_tools.py       # extract_product_fields, is_affirmative/negative
├── io/
│   ├── asr.py             # faster-whisper wrapper (offline-capable)
│   ├── ocr.py             # pytesseract + PIL preprocessing
│   └── cli.py             # standalone IO smoke tool
├── config/agent.yaml      # runtime config (session.store=inmem by default)
└── tests/                 # pytest suite (≈64 tests + 2 expected skips)
```

### 3.1 Import-graph invariants (enforced by tests)

Inside `backend/agent/` the allowed import directions are:

```
cli           ──► orchestrator, io, schemas
orchestrator  ──► planner, memory, tools, schemas
planner       ──► schemas                      (NEVER tools, NEVER io)
tools/*       ──► schemas, tools/_store        (NEVER planner, NEVER io)
io/*          ──► schemas                      (NEVER planner, NEVER tools)
memory        ──► schemas                      (NEVER planner, NEVER tools)
```

Why each forbidden arrow exists:

planner → tools : The LLM (or its parser) could trigger a write by emitting Python, not just ToolCall JSON.
tools → planner :  Tools would stop being pure functions of their Pydantic input. 
io → planner and `agent/io/ : would become non-deterministic and harder to unit-test. 
memory → tools : Session save/load could side-effect on the catalog.

These rules are validated by backend/agent/tests/test_architecture.py,
which walks the AST of every module and fails CI on any forbidden import.

### 3.2 Turn loop (deterministic order)

```
┌─────────────────────────── ONE TURN ───────────────────────────┐
│                                                                 │
│  cli.py reads input (text  ──► raw string                       │
│                       voice ──► io.asr.transcribe(wav))         │
│                       image ──► io.ocr.extract(jpg))            │
│                                                                 │
│  orchestrator.handle_turn(session_id, role, text):              │
│                                                                 │
│  1. load session   ─────► memory.load(session_id)               │
│                                                                 │
│  2. CONFIRMATION SHORT-CIRCUIT (skips the planner entirely)     │
│       if session.pending_action exists:                         │
│         is_affirmative(text)   → run staged tool, clear, return │
│         is_negative(text)      → drop staged tool, return       │
│                                                                 │
│  3. PLANNER LOOP (bounded by safety.max_tools_chain_depth)      │
│       a. build prompt: system_{role}.txt                        │
│                       + rolling history (replayed as JSON)      │
│                       + scratchpad of prior tool results        │
│                       + the new user message                    │
│       b. planner.run(prompt) → raw_llm_output                   │
│       c. _safe_parse → PlannerOutput                            │
│            (balanced-brace extractor on prose-wrapped JSON,     │
│             one repair-retry on Pydantic failure;               │
│             second failure → canned "rephrase" reply)           │
│       d. for call in planner_output.tool_calls:                 │
│            - unknown tool         → ToolResult(ok=False)        │
│            - forbidden for role   → ToolResult(ok=False)        │
│            - requires_confirm     → stage as pending_action     │
│                                     return staged=True (no run) │
│            - else                 → validate args, run, append  │
│                                     result to scratchpad        │
│       e. stop when planner emits no more tool_calls OR          │
│          assistant text is set OR depth cap reached.            │
│                                                                 │
│  4. save_session(session)  ──► memory.save(...)                 │
│                                                                 │
│  5. return TurnResponse(assistant, staged?, tool_results[])     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 LLM client precedence (env-driven) : 

`CIRCUIT_CLIENT_ID` + `CIRCUIT_CLIENT_SECRET` + `CIRCUIT_APP_KEY` all set | `CircuitClient` | Basic-auth token → `/openai/deployments/{model}/chat/completions` with `api-key` header and `app-key` JSON-encoded in `body.user` |
`OPENAI_API_KEY` set and `llm.planner.provider == "openai"` | `OpenAIClient` | Standard OpenAI `chat.completions` |
otherwise | `StubLLMClient` | Deterministic empty plan (offline grading) |

The selected client name is printed to stderr on REPL startup so a grader
always sees which backend is live.

### 3.4 Session store

Default `session.store: "inmem"`. Selecting `"redis"` triggers an active
`redis.asyncio.Redis.ping()` at startup; on failure we log a single warning
to stderr and fall back to `InMemoryStore` rather than crashing mid-turn.
This makes misconfiguration *visible at boot*, never silent and never
mid-conversation.

## 4. Tool catalog (baseline)

Each tool in `backend/agent/tools/*` carries six attributes the orchestrator
uses to gate execution:

`name` (snake_case) : Stable handle the LLM uses in `ToolCall.name`.
`input_model` (Pydantic) : Validates LLM-supplied args before the tool runs.
`output_model` (Pydantic) : Validates the result before it reaches the LLM. 
`allowed_roles` (set) : Registry hides this tool from prompts for other roles.
`requires_confirm` (bool) : Orchestrator stages the call into `pending_action` instead of executing.
`side_effect` (`read` / `write`) : Used by logs + the architectural test that no `write` tool is reachable from `cli.py` without confirmation. 

Tools shipped in this feature:

| `add_product` | vendor | write | **yes** |
| `get_my_catalog` | vendor | read | no |
| `search_products` | customer | read | no |
| `get_store` | customer | read | no |
| `extract_product_fields` | (nlp helper) | read | no |
| `is_affirmative` / `is_negative` | (nlp helper) | read | no |

### 4.1 Authorization (server-side, not LLM-side)

`vendor_tools.add_product` enforces `session.user_id == store.vendor_id` in
Python. The LLM is **never** trusted to enforce authorization. A vendor B
asking the agent to mutate vendor A's catalog results in a
`ToolResult(ok=False, error="forbidden_for_role:vendor")`, even if the LLM
emitted the call.

### 4.2 Confirmation gating (orchestrator-side, not LLM-side)

`PendingAction` lives in the session, not in the LLM's context window. The
LLM's job is to *describe* the staged action; only the orchestrator can
transition it from "staged" to "executed".

```python
class PendingAction(BaseModel):
    tool:       str
    args:       dict[str, Any]
    staged_at:  datetime
    expires_at: datetime              # default: 5 minutes
```

If the user's next turn is not a clear affirmative within `expires_at`, the
action expires silently and the user must restate it.

## 5. Acceptance criteria (testable)

1. `pip install -e ".[dev,agent]"` succeeds against the pinned versions.
2. `make test` is green: feature 000 health tests **and** feature 002 agent
   tests. The 002 suite has ≈64 passing tests and 2 known skips
   (intentional TODOs declared in `tests/test_schemas.py`).
3. `make lint` is clean across the whole repo.
4. `make run` continues to serve `/health` → `200 {"status":"OK"}` with no
   regression on feature 000.
5. Vendor REPL flow (end-to-end):
   ```
   you> add 10 kg masuri rice 58/kg
   bot> Listing: masuri rice — 10 kg @ ₹58. Reply "yes" to add or "no" to cancel.
   you> yes
   bot> Listed ✅  masuri rice (10 kg) @ ₹58 — product id: prod_<8 hex>
   ```
6. Customer REPL flow returns ranked rows when a matching product exists:
   `<n>. <store_name?> — <name> — ₹<price> — <distance_km> km`.
7. `/voice tests/fixtures/sample_voice.wav` prints a transcription banner
   with confidence and forwards the text as a user turn.
8. `/image tests/fixtures/sample_image.jpg` prints an OCR banner and
   forwards the recognised text as a user turn.
9. A turn proposing `add_product` is **never** executed on the same turn —
   `_dispatch` returns `staged=True` and `session.pending_action` is set.
   Locked down by `test_orchestrator.py::test_add_product_is_staged_only`.
10. The Circuit client wire format is locked down by 11 offline tests in
    `tests/test_planner_circuit.py` (Basic-auth, deployment URL, `api-key`
    header, `app-key` in body.user, token refresh, 401 retry).

## 6. Safety invariants

1. Every LLM response is parsed via `PlannerOutput.model_validate(...)`. A
   failure triggers exactly **one** repair attempt with a "fix your JSON"
   nudge; a second failure returns a polite fallback. The LLM cannot bypass
   the schema.
2. Every tool's args are re-validated against `tool.input_model` before the
   function body runs. The LLM cannot pass shapes the tool didn't declare.
3. Tools marked `requires_confirm: true` (currently only `add_product`) are
   stored as `session.pending_action` and only executed on a subsequent
   turn where `is_affirmative()` matches. An `is_negative()` turn drops the
   action.
4. Role gating: `tool.is_allowed_for(session.role)` is checked before
   dispatch **and** before confirmed execution (handles role-change races).
5. Anything from the user (transcribed voice, OCR'd image, raw text) is
   wrapped in `<<<UNTRUSTED>>> … <<<END>>>` before being passed to the LLM
   (prompt-injection containment).
6. Per-turn caps: `safety.max_tool_calls_per_turn` (default 4) and
   `safety.max_tools_chain_depth` (default 3) bound runtime + cost.

### 6.1 Safety enforcement summary

| LLM output is untrusted | `planner._safe_parse` validates `PlannerOutput`, orchestrator re-validates each tool's `input_model` before running. |
| Prompt injection | Tool outputs replayed to the LLM are wrapped in `<<<UNTRUSTED>>> … <<<END>>>` by `orchestrator._format_scratchpad`. |
| Authz | Inside each `vendor_tools.*` function — never delegated to the LLM. |
| Confirmation gate | Orchestrator checks `session.pending_action` before running any `requires_confirm=True` tool. |
| Rate limits | `safety.max_tools_chain_depth` + `safety.max_tool_calls_per_turn` in `agent.yaml`. |
| Secrets | Loaded from `.env` (gitignored) via `python-dotenv`; only `.env.example` placeholders are tracked. |

## 7. Configuration knobs (`backend/agent/config/agent.yaml`)

The canonical source is the YAML file. Highlights:

- `llm.planner.{provider, model, temperature_tool, temperature_chat, max_output_tokens, timeout_s}`
- `llm.asr.{engine, model, model_path, device, compute_type, beam_size, language_hint, low_confidence_threshold, max_audio_bytes, max_duration_seconds}`
- `llm.ocr.{engine, lang, psm, oem, min_chars, max_image_bytes}`
- `session.{store, redis_url, ttl_seconds, max_turns_in_context, summarize_after_turns}`
- `safety.{max_tool_calls_per_turn, max_tools_chain_depth, require_confirmation_for, rate_limit}`

CLI overrides via `--override key.subkey=value`, e.g.
`--override llm.planner.provider=openai`.

Hard rule: **no tuneable behaviour hard-coded inside `backend/agent/`.**

## 8. Failure-mode :

A flat reference of every place a turn can fail and what the agent does:

| Voice clip silent or noisy (`confidence < low_confidence_threshold`) | `io/asr.py` | "Sorry, I couldn't hear that clearly — try again or type it." |
| OCR returns `< min_chars` chars | `io/ocr.py` | "I couldn't read any text in that image — could you type it?" |
| LLM emits invalid JSON | `planner._safe_parse` (one repair retry) | Canned "Sorry, can you rephrase?" on second failure |
| LLM calls a tool not allowed for the current role | `tools.REGISTRY` + orchestrator | Log `forbidden_for_role`; emit `ToolResult(ok=False)`; ask user to clarify |
| Tool args fail Pydantic validation | Orchestrator (before `tool.run`) | "Some of those details look off — could you confirm the price/quantity?" |
| `requires_confirm` tool, no matching `pending_action` | Orchestrator | Stage action, ask "yes/confirm?" — **no write** |
| Vendor tries to mutate someone else's row | `vendor_tools.*` | `ToolResult(ok=False, error="forbidden_for_role:vendor")` |
| Tool chain exceeds `safety.max_tools_chain_depth` | Orchestrator | Canned "Let me circle back — what would you like to do next?" |
| Redis unreachable at boot when `session.store=redis` | `memory.build_store` | Single stderr warning; fall back to `InMemoryStore`; CLI keeps running |

Each row maps to one structured log event with a correlation ID.

## 9. Out-of-scope risks accepted

1. **No durable storage.** Process restart wipes session and catalog. SPEC §4
   flags `backend/app/models/` as `later`; a future DB feature will replace
   `tools/_store.py` without touching the planner contract.
2. **No HTTP exposure.** Without a `/agent/turn` route the agent cannot be
   invoked from the future React frontend yet. Accepted; a future feature
   adds the route + OpenAPI export.
3. **Provider variability.** Different LLM backends produce different
   quality. The planner contract (JSON envelope, safe-parse, repair retry)
   bounds the blast radius; the stub client gives deterministic offline
   grading.
4. **Whisper / Tesseract install weight.** Pinned in the `agent` extra so
   feature-000 graders aren't forced to install them.

## 10. Local development

```bash
# Install
pip install -e ".[dev,agent]"

# Run the vendor REPL with the stub planner (no API keys needed)
python -m backend.agent.cli --role vendor

# Run the customer REPL against OpenAI
OPENAI_API_KEY=sk-... python -m backend.agent.cli --role customer

# Run all fast tests (excludes the @pytest.mark.slow tests by default)
make agent-test

# Run only the agent slice
pytest backend/agent/tests -q
```

## 11. Governance trail

- `plan.md` — pre-flight dry-run for this feature.
- `prompts.md` — chronological LLM prompts + recurring-interaction ranking.
- `conversation-history.md` — per-session append-only history of decisions.
- This file (`agent-spec.md`) is the architectural contract for feature 002.
