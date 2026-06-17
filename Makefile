.PHONY: run test lint

run:
	python -m backend.app.main

test:
	pytest

lint:
	ruff check .
