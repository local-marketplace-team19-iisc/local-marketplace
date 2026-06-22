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
