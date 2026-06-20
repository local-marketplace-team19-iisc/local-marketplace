# Conversation History — Feature 002: Conversational Agent

Append-only, cumulative audit log (Constitution P3). Each session is appended
below; earlier entries are never edited or removed. Newest entries go at the
bottom.

---

## Session 1 — Product framing & agent shape (2026-06-18)

### Context / goal
Convert the original idea (`abstract.txt` and the flow diagram) into a
deterministic product contract for `SPEC.md`, then decide the implementation
shape. The single binding question for this session: 
is the system a conversational agent at its core, or a CRUD app with an LLM bolted on?
The answer drives every subsequent decision — directory layout, the planner /
orchestrator split, the tool contract, and what "deterministic" means for
graders.

### Decisions made (+ reasoning)
1. **The system IS an agent.** A single planner + tools turn loop is the unit
   of truth, not a chain of REST endpoints — because every customer and
   vendor interaction is conversational, including the multimodal inputs.
2. **LLM does understanding only, writes are deterministic.** Pricing,
   inventory, confirmation gating, and the catalog state must be predictable
   for graders and customers. The planner *proposes*; the orchestrator is the
   only component allowed to *mutate*.
3. **Three baseline input modalities only.** Text, voice → text (Whisper),
   image → text (Tesseract). Everything else (payments, MCP, native
   multilingual prompts) moved to `later`. Trimming the surface up front
   prevents two weeks of spec churn.

### Edge cases / unknowns discovered
- Vendor and customer share the same REPL surface but must NOT share tools.
  An injected query like "list me as a vendor" must fail closed → role gating
  belongs at the tool dispatcher, not the prompt.
- Voice and image are *inputs*, not channels. Whichever modality the user
  picks, the downstream path is identical → one `Message(text=…)` after
  modality decode, no per-modality branching beyond the I/O boundary.

### Outcome
Spec stabilised. `002-agent/spec.md` written. The "agent as the unit of truth"
framing carries through to every later session.

---

## Session 2 — I/O modality scope (2026-06-18)

### Context / goal
Lock down the I/O contract for the three baseline modalities (text, voice,
image) so the orchestrator can treat them uniformly. The deliverable for this
session is a single, precise answer to four questions:

1. **Which engines run for voice and image?** Pick concrete libraries + model
   sizes, with offline-first defaults.
2. **Where do they run?** Local process, or a remote service? (Constraint:
   graders on a laptop must be able to demo the agent without network.)
3. **What is the orchestrator boundary?** Define the schema returned by ASR
   and OCR, the error types raised, and the confidence/quality thresholds
   that gate forwarding to the planner.
4. **What configuration knobs are needed?** Anything tuned per deployment
   (size limits, language hints, model paths) lives in `agent.yaml`, not in
   code.

### Decisions made (+ reasoning)
- **ASR engine: `faster-whisper` (CTranslate2 backend), model `base.en`.**
  Local process, no remote inference — graders can run it on a laptop.
  `base.en` is the cheapest model that hit acceptable accuracy on the sample
  fixture (`sample_voice.wav`).
- **OCR engine: `Tesseract` via `pytesseract`.** Standard, free, runs offline.
  PIL preprocessing (binarise + denoise) is hidden inside `ocr.py` so the
  orchestrator sees a plain `str`.
- **Confidence-aware ASR.** Below `low_confidence_threshold` (0.6) the CLI
  refuses to forward the transcription and asks the user to retype, rather
  than handing garbage to the planner. Deliberate choice to make voice
  failures *loud*.
- **Offline model path support.** Added `llm.asr.model_path` so a
  pre-downloaded weights directory is used instead of pulling from HF Hub at
  runtime. Critical for corporate networks where HF is blocked.
- **System dependencies documented, not auto-installed.** `ffmpeg` (Whisper
  audio decode) and `tesseract` (OCR engine) are README pre-requisites. The
  Python wrappers are pinned in `pyproject.toml`; we never shell out to a
  package manager from code.

### Edge cases / unknowns discovered
- Audio size and duration limits need to live in config, not code — otherwise
  we cannot tune them per deployment. Moved to
  `llm.asr.{max_audio_bytes, max_duration_seconds}`.
- `pytesseract` raises a generic `RuntimeError` when the `tesseract` binary
  is missing from `PATH`. Wrapped with a dedicated `OCRDependencyError` so
  the CLI can print a humane "install with `brew install tesseract`" message
  instead of a stack trace.

### `[NEEDS CLARIFICATION]` raised / resolved
- (raised) Multilingual OCR (`eng+kan` for Kannada). **Resolved** to
  English-only at baseline; `lang` remains configurable for future enabling.

---

## Session 3 — Agent core implementation (2026-06-19)

### Context / goal
Design and implement the planner / orchestrator / tools stack end-to-end and
ship a test suite that proves the invariants.
Before this session the project held only specifications. The deliverable is a working `python3 -m
backend.agent.cli` REPL whose behaviour is bounded by code, not prompts.

Scope this session covers:

1. **Planner.** Build the LLM-facing JSON contract (`PlannerOutput`) and a
   provider-agnostic client interface so OpenAI, Cisco Circuit, and a stub
   client can be swapped via environment variables without orchestrator
   changes.
2. **Orchestrator.** Implement the turn loop — load session, detect a
   pending confirmation, run the planner, dispatch tool calls (with
   role-gating and confirmation-staging), and persist the turn. Bound the
   inner loop by `safety.max_tools_chain_depth`.
3. **Tools layer.** Provide a `@tool` decorator and `REGISTRY` so each tool
   declares its Pydantic input / output models. The orchestrator
   re-validates arguments at dispatch time; tools never trust the LLM
   directly.
4. **Test suite.** Unit tests for the schemas, the tools, and
   `is_affirmative`/`is_negative`; orchestrator tests with a `ScriptedLLMClient`
   that asserts confirmation gating, role enforcement, and explicit
   cancellation; planner tests with an offline `httpx` stub.

Out of scope for this session: real LLM integration (provider clients exist
but only `StubLLMClient` is exercised end-to-end here), persistence beyond
in-memory, and the HTTP surface.

### Decisions made (+ reasoning)
- **`PlannerOutput` is the LLM contract.** Pydantic-validated, with exactly
  three fields: `thought`, `tool_calls[]`, `assistant`. The LLM never gets to
  decide the shape — anything else is a parse error.
- **`@tool` decorator + `REGISTRY`.** Each tool declares `input_model` and
  `output_model`. The orchestrator re-validates args at dispatch time, so the
  tool body can trust its inputs. Forgetting `input_model` is a registration
  failure, not a silent crash.
- **Confirmation gating is the orchestrator's job, not the prompt's.** Tools
  marked `requires_confirm: true` get *staged* (stored as
  `session.pending_action`); the orchestrator runs them on the next turn that
  passes `is_affirmative()`. The LLM is told to call them; the LLM is *not*
  trusted to skip them.
- **`StubLLMClient` for tests and offline grading.** Deterministic empty
  plan. Lets us run `pytest` without an LLM provider. Selection is printed to
  stderr on REPL startup so the grader knows which backend ran.
- **In-memory store as the default.** No Redis dependency to demo the agent.

### Edge cases / unknowns discovered
- `is_affirmative()` originally returned a *list* (truthy but not a bool),
  which silently broke the orchestrator's confirmation branch. Fixed with a
  test that asserts the return type (`test_tools_vendor.py`).
- The sandbox's system Python (3.9) couldn't parse Python 3.10+ `match`
  statements in `huggingface_hub`. We scoped AST checks to project sources
  only.

### Outcome
First full pytest pass: 64 tests, 2 expected skips. The CLI runs locally
against the stub client.

---

## Session 4 — Circuit gateway integration, first attempt (2026-06-19)

### Context / goal
Wire the agent to the Circuit (egai) gateway so the planner can run
against gpt-4o-mini on the corporate network without changing orchestrator
or tool code. 
Deliverable: a CircuitClient selected automatically when the
CIRCUIT_* environment variables are set, with the same (text, usage)
return contract as OpenAIClient so the planner is provider-agnostic.

### Decisions made (+ reasoning)
- **Tried the obvious OAuth2 Bearer convention.** Form-body
  `grant_type=client_credentials` + `client_id` + `client_secret`; chat URL
  `/v1/chat/completions`; `Authorization: Bearer …`; `app-key` header.
- **Cached the token in-process** with a refresh margin and a single-flight
  `asyncio.Lock` so concurrent turns don't stampede the token endpoint.
- **Wrote offline tests** to lock down the wire format against a stubbed
  `httpx` so we never have to hit the gateway to ship a change.

### Edge cases / unknowns discovered
- The gateway responded `401 { fault: Failed to Resolve Variable :
  policy(JWT-validateToken) variable(oauthtoken) }`. First debug guess was a
  header-name issue — added a `CIRCUIT_TOKEN_HEADER` knob defaulting to
  `oauthtoken`. **Wrong call.** The 401 persisted in the REPL even though
  every offline test passed. Lesson recorded: when the gateway error names a
  "variable", it's an Apigee `ExtractVariables` policy failure, and it
  cannot be fixed by re-arranging headers blindly. Need a working reference.

### Outcome
Circuit integration still broken at end of session. Marked as the next
session's first priority; explicitly asked the user for a working reference
from a project where Circuit is known to work.

---

## Session 5 — Circuit gateway integration, evidence-based fix (2026-06-20)

### Context / goal
Stop guessing. Read the working Circuit caller in DDTSAutomation
(`xrSanity2_Project/DDTSMgmt_Backend/llm_description_Genration/
Headline-Desc_CircuitApi.py`) and mirror its wire format same. 
Replace every assumption from above session with a behaviour observed in code that is
known to talk to the same gateway successfully.

### Decisions made (+ reasoning)
- **Circuit is an Azure-OpenAI passthrough, not a custom egai layer.** Every
  surprise in our previous attempt traces back to this.
- **Token endpoint:** `Authorization: Basic base64(id:secret)` + body
  `grant_type=client_credentials` (client_id / secret never travel in the
  body). The form-fields branch was deleted.
- **Chat URL:** `{CHAT_URL}/openai/deployments/{model}/chat/completions` —
  the deployment name lives in the URL, not the body.
- **Chat auth header:** `api-key: <token>` (no `Authorization`, no
  `oauthtoken`). This was the single line that closed the 401.
- **`app-key` location:** inside `body.user` as `json.dumps({"appkey": …})`,
  not as a header.
- **Drop `response_format=json_object`.** The deployment rejects unknown
  fields on some routes. JSON discipline is enforced by the system prompt +
  `_safe_parse` only.
- **Proxy and TLS knobs.** Honour `HTTPS_PROXY` from env; allow opt-out of
  TLS verification via `CIRCUIT_VERIFY_SSL=false` (matches the DDTSAutomation
  reference's corporate-proxy needs without making it the default).
- **Rewrote all 11 offline tests** to assert the corrected wire format —
  Basic-auth, deployment URL, `api-key`-only headers, `app-key` in body,
  401 retry uses a fresh headers dict (so test introspection sees the
  original attempt's headers, not the mutated retry).

### Edge cases / unknowns discovered
- The 401-retry path was mutating `headers["api-key"]` in place, so the test
  assertion `chat_calls[0].headers["api-key"] == "tok-1"` failed (both
  attempts saw `tok-2`). Fixed by building a fresh `retry_headers` dict.
- Token TTL of zero in the gateway response was treated as "instant expiry"
  by the old code path. Defaulted to a 30-minute TTL when `expires_in` is 0
  or missing.

### Outcome
Circuit integration verified end-to-end. The REPL prints
`info: planner using CircuitClient (model=gpt-4o-mini,
chat_url=https://chat-ai.cisco.com)` on startup; the first turn round-trips
real text.

---

## Session 6 — Runtime robustness (Redis fallback + prompt drift) (2026-06-20)

### Context / goal
Two production-grade rough edges surfaced as soon as Circuit actually worked:

1. The agent crashed mid-turn on redis.exceptions.ConnectionError because
   agent.yaml shipped with session.store: "redis" and the I had
   no Redis running locally.
2. The vendor REPL accepted an add_product request, summarised it
   conversationally, accepted "yes", and then failed to actually list the
   product — and the *next* add_product turn returned "Sorry, could you
   rephrase that?".

Goal for this session: make both failure modes impossible by default. The
agent should run with zero sidecars, and a single bad LLM reply must not
poison the next turn.

### Decisions made (+ reasoning)
- **Flipped the default `session.store` to `"inmem"`.** Production Redis is
  great; requiring a sidecar to run the REPL is not. The Redis branch is
  still supported.
- **`build_store` actively probes Redis at startup.** Lazy clients defer
  errors to the first I/O — meaning a wrong URL only crashes once you're
  three turns deep. Replacing that with `asyncio.run(store._r.ping())` and a
  stderr warning on fallback makes the failure mode visible up front.
- **Fixed the contradiction between the vendor system prompt and the
  orchestrator.** The prompt was telling the LLM *not* to emit `add_product`
  on the staging turn; the orchestrator was relying on `requires_confirm` to
  stage that very call. Rewrote `system_vendor.txt` with a worked example
  showing the correct single-turn output (parse + stage + assistant
  preview).
- **Strengthened `_safe_parse`.** Added a balanced-brace extractor for the
  case where the LLM wraps its JSON in prose. The strict parse remains the
  primary; this is a safety net, not the default path.
- **Stopped feeding prose back into the model.** `_build_messages` now
  replays each past assistant turn as the JSON envelope the planner is
  required to emit — not as the user-facing text. This kills the "model sees
  its own prose and drifts" failure mode within a few turns.

### Edge cases / unknowns discovered
- **The "yes" appeared to work but didn't.** First sign was that the bot
  reply was prose ("Your order for 10 kg of sugar has been confirmed.")
  rather than the orchestrator's `"Listed ✅ …"` template. Reading the
  template told us the staging never happened — meaning the LLM was never
  emitting `add_product`. That detective work is now encoded in the Worked
  Example block of the system prompt.
- **History pollution is a real failure mode, not a theoretical one.**
  After two prose turns the LLM had effectively re-trained itself to reply
  in prose, which is why the second `add_product` turn parse-failed.

### Outcome
End-to-end flow verified:

```
you> add 10 kg masuri rice 58/kg
bot> Listing: masuri rice — 10 kg @ ₹58. Reply "yes" to add or "no" to cancel.
you> yes
bot> Listed ✅  masuri rice (10 kg) @ ₹58 — product id: prod_<8 hex>
```

`/catalog` shows the row. 64 tests + 2 skips still green.
