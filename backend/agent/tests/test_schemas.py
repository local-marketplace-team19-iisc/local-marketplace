"""Pydantic validation contracts. See spec.md §6 (Data Model)."""
from __future__ import annotations

import pytest


def test_schemas_module_imports() -> None:
    """Smoke test: every Pydantic model in agent.schemas should import."""
    schemas = pytest.importorskip("agent.schemas")
    assert hasattr(schemas, "__name__")


@pytest.mark.skip(reason="TODO: assert ProductDraft rejects negative price")
def test_product_draft_rejects_negative_price() -> None: ...


@pytest.mark.skip(reason="TODO: assert Session.role is one of {vendor,customer,unknown}")
def test_session_role_enum() -> None: ...
