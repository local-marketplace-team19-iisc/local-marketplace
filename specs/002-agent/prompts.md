# Prompts — Feature 002: Conversational Agent

Maintain a chronological log of all feature-defining LLM prompts (Constitution P3). For each prompt, keep the original text and add:

   Deliverable: what must be produced.
   Acceptance: how completion is verified.
   Constraint: any explicit scope limitations.

Recurring intents are ranked at the bottom and flagged
[SKILL CANDIDATE] when they recur ≥ 3 times.

## Chronological log

### Phase A — Specification (DL_Project)

1. "Analyse `abstract.txt` and `AI-Driven NLP-Based Local Marketplace.png`
   and update `spec.md` with architecture, plan, tech and implementation —
   clean and clear."
   - Deliverable: DL_Project/spec.md rewritten from the idea-doc
     and flow-diagram inputs.
   - Acceptance: File contains four named sections — Architecture,
     Plan, Tech stack, Implementation — and no TODOs or placeholders.
   - Outcome: Marketplace product spec drafted; chatbot-led model
     and Bangalore hyperlocal scope locked.

2. Create a production-ready agent that owns the entire workflow end-to-end, from user input through planning, orchestration, tool execution, validation, and response generation. Use gpt2-post-training/SPEC.md as the reference implementation for architecture, code organization, testing standards, documentation, and delivery quality. The result should be a fully implemented and thoroughly tested system, not just a specification or prototype
   - Deliverable: DL_Project/AGENT_SPEC.md modelled on
     gpt2-post-training-Akuu269-main/SPEC.md's section structure.
   - Acceptance: Spec names the planner, orchestrator, and tools
     contracts, and the role-gating model (vendor vs customer).
   - Constraint: LLM is restricted to understanding, all writes go
     through deterministic tool calls.
   - Outcome: AGENT_SPEC.md authored, the "LLM does understanding,
     code does writes" invariant locked as binding.

3. Removed payments and MCP from the feature list — and update agent-spec.md"
   - Deliverable: `agent-aspec.md` payments / Model-Context-Protocol feature removed.
   - Acceptance: rg -i 'payment|mcp' over file returns zero
     hits, and no section cross-reference is left dangling.
   - Outcome: agent-specs scrubbed, orphaned references cleaned.

4. Scope Decision: Baseline Input Modalities

Define the v1 input surface in agent-spec.md (Input Modalities).

   Deliverable : 

   Update agent-spec.md §2 to include exactly three supported v1 modalities:
      Text → Text
      Voice → Text
      Image → Text

   Acceptance : 

   The Input Modalities table contains exactly three v1 entries.
   Voice input is represented as voice-to-text only.
   Image input is represented as image-to-text only.
   All other modalities are listed under a dedicated Future, Later, or Out of Scope section.

   Constraints : 

   Do not include native audio understanding, multilingual processing, video inputs, vision-language models, or any other modality in the v1 implementation scope.
   Do not define APIs, infrastructure, or workflows for deferred modalities beyond a brief future-state description.

   Rationale : 

   Lock the baseline scope to three modalities to reduce implementation complexity and ensure a well-defined, testable v1. All additional modalities are explicitly deferred to future releases.

5. Define and document the baseline repository layout in agent-spec.md to serve as the single source of truth for all feature implementations.

   Deliverable : 

   Add a canonical project-tree section to agent-spec.md containing:
   backend/
   backend/agent/
   frontend/
   specs/
   tests/
   scripts/
   Include a one-line purpose description for each directory.

   Acceptance : 

   spec.md contains a single authoritative repository tree.
   Every listed directory includes a clear ownership/purpose note.
   Subsequent features reference paths from this tree rather than introducing new top-level structures or inconsistent locations.

   Constraints : 

   Do not define feature-specific implementations in this section.
   Do not introduce additional top-level directories unless explicitly approved through a future specification update.

   Rationale : 

   Establish a stable repository contract early so that all future specifications, implementations, and tests share a consistent filesystem layout and naming convention.

6. Scope Decision: Design Review Only

   Provide a high-level implementation walkthrough covering the proposed architecture, execution flow, and design decisions without making any repository changes.

   Deliverable : 

      A chat-only design discussion describing:
      Conversational turn loop
      Confirmation and approval gating
      Tool registry and tool-selection strategy
      Planner and orchestrator interaction
      Execution lifecycle and error handling

   Acceptance : 

      The design is fully explained in chat.
      No files are created, modified, renamed, or deleted.
      No specifications, code, tests, or documentation are updated as part of this request.

   Constraints : 

      Read-only review mode.
      Discussion and planning only, implementation is explicitly out of scope.

### Phase B — I/O modalities (ASR + OCR)

8. Scope Decision: Input Processing & Modality Contract

   Define the end-to-end input lifecycle for all supported v1 modalities and document how inputs transition from user submission to agent processing.

   Deliverable : 

   Update specs/input-spec.md and specs/agent-spec.md with a standardized four-stage I/O contract covering:
   User entry points (vendor and customer flows)
   Orchestrator intake and modality routing
   LLM-driven OCR/ASR invocation decisions
   Normalization into a canonical Message(text=...) payload

   Acceptance : 

   Text, Voice → Text, and Image → Text are each documented separately.
   Each modality specifies:
   Entry point by user role (vendor/customer)
   Orchestrator boundary and routing behavior
   Conditions under which the LLM triggers OCR or ASR processing
   Post-conversion handoff into the agent as Message(text=...)
   Both specification files describe the same canonical processing contract.

   Constraints : 

   Limit scope to the three approved v1 modalities.
   Do not introduce native audio understanding, video processing, multilingual pipelines, or vision-language reasoning.
   All modalities must converge into a single text-based agent interface.

   Rationale

   Establish a consistent modality-ingestion contract so that all user inputs, regardless of source, are normalized into text before entering the planner, orchestrator, and tool-execution workflow.

9. Scope Decision: I/O Implementation with Decision Gating

   Implement the v1 input pipeline (Text, Voice → Text, Image → Text) only after all configurable design choices have been explicitly reviewed and approved.

   Deliverable : 

   Implement text, ASR, and OCR input modules.
   Add terminal-based smoke tests demonstrating successful processing of:
   Text input
   Voice → Text conversion
   Image → Text conversion
   Conduct a decision-confirmation review before implementation begins.

   Acceptance : 

   Every configurable parameter is documented and approved before any code changes are made, including:
   ASR engine and model selection
   OCR engine and language packs
   Online vs. offline execution mode
   Model locations and loading strategy
   File-size, duration, and payload limits
   Supported languages and normalization rules
   No implementation, testing, or file modification occurs until all decisions receive explicit confirmation.
   Terminal smoke tests pass for all three supported modalities.

   Constraints : 

   Zero implicit defaults.
   No assumptions about engines, models, languages, limits, or runtime behavior.
   Implementation is blocked until decision review and approval are completed.

10. Scope Decision: Offline Whisper Model Provisioning

   Provision ASR models ahead of time and ensure runtime operation is fully offline.

   Deliverable : 

   Add scripts/download_whisper_base_en.sh to download and stage Whisper model assets locally.
   Add an llm.asr.model_path configuration entry to agent.yaml.
   Configure ASR initialization to load models exclusively from the configured local path.

   Acceptance : 

   Whisper model files can be downloaded and stored using the provided script.
   ASR loads successfully from llm.asr.model_path.
   No runtime downloads or requests to external model repositories occur during ASR initialization or inference.
   Offline startup is validated through a local smoke test.

   Constraints : 

   Do not depend on automatic model fetching at runtime.
   Do not require access to Hugging Face Hub or other external model registries after installation.
   Model location must be configurable rather than hardcoded.


### Phase C — Agent core (planner / orchestrator / tools)

12. Scope Decision: Agent Core Implementation

   Implement the complete conversational agent layer, including planning, orchestration, tool execution, and interactive CLI workflows.

   Deliverable : 

   Create:
   agent/schemas.py
   agent/planner.py (supporting both OpenAIClient and StubLLMClient)
   agent/orchestrator.py
   agent/tools/ (vendor, customer, NLP, and shared/base tools)
   agent/cli.py
   Establish a unified tool registry used by all agent workflows.

   Acceptance : 

   A terminal REPL supports end-to-end vendor workflows (e.g., add listing → confirm → execute).
   A terminal REPL supports end-to-end customer workflows (e.g., search → view details).
   Planner, orchestrator, and tools interact through defined contracts.
   All tool invocations are resolved through a single registry.
   End-to-end flows execute successfully using StubLLMClient without external LLM dependencies.

   Constraints : 

   The LLM may plan and recommend actions but must never perform state mutations directly.
   All mutating operations require explicit confirmation before execution.
   Tool execution must be mediated by the orchestrator and registry, direct tool access is prohibited.
   Confirmation-gating is mandatory for all create, update, and delete actions.

   Rationale

   Establish a deterministic, auditable agent architecture where the LLM drives intent and planning while the orchestrator retains authority over tool execution and state-changing operations.

### Phase D — Circuit gateway debugging

14. Issue coming in chatbot CLI:
    RuntimeError: CircuitClient chat request failed: 401 { fault:
    Failed to Resolve Variable : policy(JWT-validateToken)
    variable(oauthtoken) }
    - Deliverable: A root-cause for the 401 from the Circuit
      gateway and a code fix that eliminates it from the REPL.
    - Acceptance: A live REPL turn against Circuit completes a chat
      call with HTTP 200 and a parseable JSON envelope.
    - Outcome: First fix attempt was wrong — assumed the gateway
      wanted a custom `oauthtoken` header and added a
      `CIRCUIT_TOKEN_HEADER` knob. Tests passed; the REPL still 401-ed.
      Lesson logged: an Apigee `Failed to Resolve Variable` error is
      not a header-name problem — needed a working reference.

### Phase E — Runtime robustness

16. "fixed the redis connection error :
    redis.exceptions.ConnectionError: connecting to localhost:6379
    - Deliverable: config/agent.yaml default switched to
      session.store: "inmem" and build_store() in agent/memory.py
      hardened with a startup-time Redis health check.
    - Acceptance: The CLI starts and serves a turn with no Redis
      sidecar; if session.store: "redis" is set and the gateway is
      unreachable, the process emits a single stderr warning and
      falls back to InMemoryStore instead of crashing mid-turn.
    - Outcome: Default flipped, startup ping + graceful fallback
      shipped, misconfig is now visible at boot, not at turn time.

17. "add 10kg sugar then yes then add 10 kg masuri rice →
    "Sorry, could you rephrase that?""
    - Deliverable: A coordinated fix across agent/prompts/system_vendor.txt,
      agent/planner.py::_safe_parse, and agent/planner.py::_build_messages
      that closes both reproduced bugs.
    - Acceptance: Replaying the user's exact transcript
      (add 10kg sugar → yes → add 10 kg masuri rice) in the REPL
      produces (i) a confirmed write for sugar after yes and
      (ii) a staged add_product preview for masuri rice — neither
      turn falls into the "Sorry, could you rephrase that?" fallback.
    - Outcome: Three coordinated fixes shipped:
      1. Rewrote system_vendor.txt with a worked example so the LLM
         emits add_product on the staging turn (the orchestrator
         was already expecting it to, the prompt was telling it not to).
      2. Extended _safe_parse with a balanced-brace extractor that
         pulls JSON out of prose-wrapped replies.
      3. Rewrote _build_messages so past assistant turns are replayed
         to the planner as their JSON envelope, not as user-facing
         prose — killing the "model sees its own prose and drifts"
         failure mode.