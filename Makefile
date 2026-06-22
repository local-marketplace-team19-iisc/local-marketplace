.PHONY: run test lint agent agent-vendor agent-customer agent-test agent-lint

# ---- Feature 000 (app scaffold) -----------------------------------------
run:
	python -m backend.app.main

test:
	pytest

lint:
	ruff check .

# ---- Feature 002 (conversational agent) ---------------------------------
# `make agent` defaults to vendor role. Use `make agent-customer` for the
# customer REPL. Override the LLM client via env vars (CIRCUIT_* / OPENAI_API_KEY).
agent: agent-vendor

agent-vendor:
	python -m backend.agent.cli --role vendor

agent-customer:
	python -m backend.agent.cli --role customer

agent-test:
	pytest backend/agent/tests

agent-lint:
	ruff check backend/agent
