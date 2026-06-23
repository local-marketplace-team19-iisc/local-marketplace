# Specification: Semantic Search Backend API (`spec.md`)

## Goal
The goal of the `/api/search` backend endpoint is to provide an intelligent, intent-aware semantic discovery pipeline for the local marketplace. Instead of relying purely on literal, rigid keyword matching, this API handles natural language queries from users (e.g., *"5 kg sugar"*, *"something sweet for tea"*). It processes user intent, identifies matching product categories or subcategories using vector embeddings, and returns an optimized list of active, **in-stock items** along with complete pricing and vendor configurations.

---

## Constraints
* **Inventory Enforcements:** The system must strictly omit products where `stock_quantity <= 0`. Only available items can be served in the search results payload.
* **Input Validation Bounds:** Empty strings or queries containing only whitespace must be blocked at the API gateway layer before invoking the vector inference pipeline.
* **Pagination Strictness:** Search results pagination parameters must enforce explicit limits: maximum items per page (`limit`) cannot exceed `50`, and offset indexes (`offset`) must be non-negative integers.
* **Zero Dependency Coupling at Load-Time:** The search route architecture must load independent of heavy, non-essential dependencies (such as cryptographic submodules) to maintain decoupled execution profiles across testing suites.

---

## Project Layout
The search feature integrates into the existing ecosystem using the following structured system positions:

```text
backend/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── __init__.py       # Registers and exposes the search router module
│   │       └── search.py         # Handles HTTP requests, dependency injection, and endpoint logic
│   ├── schemas/
│   │   └── search.py             # Defines the Pydantic data validation and serialization models
│   └── main.py                   # Includes and mounts the search route router into the FastAPI application
└── tests/
    └── test_search.py            # Holds the automated validation tests for semantic matching bounds