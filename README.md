# local-marketplace

Conversational AI marketplace agent. See [SPEC.md](SPEC.md) for the product spec and
[specs/constitution.md](specs/constitution.md) for governance.

## Run (app scaffold — feature 000)

```bash
# install (Python >=3.11)
pip install -e ".[dev]"

# run the API (PORT defaults to 8000; override to rebind)
make run                 # or: python -m backend.app.main
PORT=9001 python -m backend.app.main

# verify
curl localhost:8000/health   # -> {"status":"OK"}

# tests + lint
make test                # pytest
make lint                # ruff check .
```

Optional (Docker): `docker compose up` then `curl localhost:8000/health`.

## Run (agent — feature 002)

Conversational marketplace agent (vendor/customer REPL with text, voice, and
image input). Source contract:
[specs/002-agent/agent-spec.md](specs/002-agent/agent-spec.md).

```bash
# install the agent extras (adds httpx, pydantic, faster-whisper, pillow,
# pytesseract, etc. on top of the dev extras)
pip install -e ".[dev,agent]"

# system deps (one-time, macOS Homebrew shown)
brew install ffmpeg tesseract

# (optional) pre-download Whisper weights for offline ASR — committed
# .gitignore keeps the binary out of Git.
bash scripts/download_whisper_base_en.sh

# pick a planner backend (one of the two, or neither for the stub)
cp .env.example .env
#   - set OPENAI_API_KEY=... in .env, OR
#   - set CIRCUIT_CLIENT_ID/SECRET/APP_KEY for the Cisco gateway.
```

REPL:

```bash
make agent              # vendor role (default)
make agent-customer     # customer role

# Inside the REPL:
#   /help                              show commands
#   /voice path/to/clip.wav            transcribe via Whisper
#   /image path/to/photo.jpg           OCR via Tesseract
#   /catalog                           snapshot of the in-memory product store
#   /reset                             wipe store + start a fresh session
#   /quit                              exit
```

Tests + lint scoped to the agent:

```bash
make agent-test         # pytest backend/agent/tests
make agent-lint         # ruff check backend/agent
make test               # full repo (000 + 002)
```

## Run (SBERT lightweight router — feature 008)

The V1 natural-language agent for the marketplace (text + voice → SBERT →
intent + entities → existing APIs). Replaces feature 007's planner-backed
chat endpoint with a stateless, LLM-free pipeline. Source contract:
[specs/008-sbert-intent-router/spec.md](specs/008-sbert-intent-router/spec.md).

```bash
# install SBERT + numpy (~500 MB closure; one-time)
make sbert-install

# pre-download the model (~80 MB) into ./models/sbert so the app boots
# offline and CI doesn't hit the network. Requires huggingface.co access.
make sbert-download

# run the API — three new routes are exposed:
#   POST /api/chat              — chatbot (frontend-compatible shape)
#   POST /api/agent/route       — verbose one-shot router (debug/tool callers)
#   GET  /api/search?q=...      — search-bar (anonymous-friendly)
make run

# fast unit tests for the router
make router-test

# end-to-end SBERT accuracy gate (requires model pre-downloaded or
# ALLOW_MODEL_DOWNLOAD=1 in the environment)
make sbert-test
```

Configuration knobs live in `.env.example` under the feature 008 section:
`MODELS_DIR`, `ALLOW_MODEL_DOWNLOAD`, `SBERT_MODEL_NAME`,
`INTENT_CONFIDENCE_THRESHOLD`, `CATEGORY_MATCH_THRESHOLD`,
`AGENT_CHAT_TURN_TIMEOUT_S`.

The products API the router talks to is the real feature
006-vendor-product-management service
(`backend/app/services/product_service.py` + `backend/app/api/routes/products.py`
and `backend/app/api/routes/catalog.py`). The SBERT router dispatches into it
directly against a SQLAlchemy `Session` — no HTTP self-call.
