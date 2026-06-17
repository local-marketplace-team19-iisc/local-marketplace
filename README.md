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
