.PHONY: install dev run test lint \
        docker-build docker-up docker-down \
        db-migrate test-db \
        agent agent-vendor agent-customer agent-test agent-lint

# ---------------------------------------------------------------------------
# Corporate proxy (optional).
# Outside a corporate network leave PROXY unset — builds go direct.
# On a network with a proxy: make docker-build PROXY=http://proxy.example.com:8080
# ---------------------------------------------------------------------------
PROXY ?=

ifneq ($(PROXY),)
BUILD_PROXY_ARGS := --build-arg http_proxy=$(PROXY) \
                    --build-arg https_proxy=$(PROXY) \
                    --build-arg no_proxy=localhost,127.0.0.1
else
BUILD_PROXY_ARGS :=
endif

# ---- Feature 000 (app scaffold) ------------------------------------------
install:
	pip install -e ".[dev]"

dev:
	uvicorn app.main:app --app-dir backend --port $${PORT:-8000} --reload

run:
	python -m backend.app.main

test:
	pytest

lint:
	ruff check .

# ---- Feature 001 (db schema) — container + migration lifecycle -----------
# Requires Podman 5.5+ (macOS: ensure `podman machine start` first).
# Image pulls bypass the host proxy (direct registry access).
# Build RUN steps use the proxy via BUILD_PROXY_ARGS if PROXY is set.
docker-build:
	env -u HTTP_PROXY -u HTTPS_PROXY podman pull --tls-verify=false python:3.11-slim
	env -u HTTP_PROXY -u HTTPS_PROXY podman pull --tls-verify=false postgis/postgis:16-3.4
	podman build --pull=never $(BUILD_PROXY_ARGS) \
	  -t local-marketplace-db -f backend/db/Dockerfile .
	podman build --pull=never $(BUILD_PROXY_ARGS) \
	  -t local-marketplace-backend -f Dockerfile .

docker-up:
	podman run -d --name marketplace-db \
	  -e POSTGRES_USER=$${POSTGRES_USER:-marketplace} \
	  -e POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:-marketplace} \
	  -e POSTGRES_DB=$${POSTGRES_DB:-marketplace} \
	  -p 5432:5432 \
	  -v marketplace-pgdata:/var/lib/postgresql/data \
	  -v $(PWD)/backend/db/init:/docker-entrypoint-initdb.d \
	  local-marketplace-db

docker-down:
	podman stop marketplace-db 2>/dev/null || true
	podman rm marketplace-db 2>/dev/null || true

db-migrate:
	alembic upgrade head

test-db:
	pytest backend/tests/db/ -v

# ---- Feature 002 (conversational agent) ----------------------------------
agent: agent-vendor

agent-vendor:
	python -m backend.agent.cli --role vendor

agent-customer:
	python -m backend.agent.cli --role customer

agent-test:
	pytest backend/agent/tests

agent-lint:
	ruff check backend/agent
