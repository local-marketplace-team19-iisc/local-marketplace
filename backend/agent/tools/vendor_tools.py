"""Vendor-only tools (baseline).

Baseline scope (see `FEATURES.md` Feature-5 + this round's plan):
- `add_product` — confirmation-gated write. Persists into the in-memory
  `agent.tools._store`. A vendor's first product auto-creates a default
  store for them (full `create_store` UX is deferred to a later round).
- `get_my_catalog` — read-only list of the current vendor's products.

Deferred to a later round (still importable but registered nowhere):
- `create_store`, `update_product`, `delete_product`, vendor registration.

Authz rule (server-side, never delegated to the LLM):
- `add_product` resolves the store via `ToolContext.user_id`. There is no
  way for the LLM to write to a store it doesn't own — the vendor_id ->
  store mapping is computed here, not supplied by the planner.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from backend.agent.schemas import Product, ProductDraft
from backend.agent.tools import _store
from backend.agent.tools.base import ToolContext, tool


# --------------------------------------------------------------------------- #
# add_product (confirmation-gated)
# --------------------------------------------------------------------------- #


@tool(
    name="add_product",
    input_model=ProductDraft,
    output_model=Product,
    roles=["vendor"],
    side_effect="write",
    requires_confirm=True,
    description=(
        "Persist a previewed product to the vendor's catalog. The planner "
        "MUST first present the draft and wait for an explicit 'yes' before "
        "calling this tool (the orchestrator enforces this regardless)."
    ),
)
async def add_product(args: ProductDraft, ctx: ToolContext) -> Product:
    vendor_id = ctx.user_id or "anon_vendor"
    store = _store.get_or_create_default_store(vendor_id=vendor_id)
    now = datetime.now(timezone.utc)
    product = Product(
        **args.model_dump(),
        product_id=_store.next_product_id(),
        store_id=store.store_id,
        created_at=now,
        updated_at=now,
    )
    _store.put_product(product)
    return product


# --------------------------------------------------------------------------- #
# get_my_catalog (read-only)
# --------------------------------------------------------------------------- #


class CatalogIn(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CatalogOut(BaseModel):
    products: list[Product] = []
    total: int = 0


@tool(
    name="get_my_catalog",
    input_model=CatalogIn,
    output_model=CatalogOut,
    roles=["vendor"],
    side_effect="read",
    description="List the current vendor's products (paginated).",
)
async def get_my_catalog(args: CatalogIn, ctx: ToolContext) -> CatalogOut:
    vendor_id = ctx.user_id or "anon_vendor"
    all_products = _store.products_for_vendor(vendor_id)
    total = len(all_products)
    sliced = all_products[args.offset : args.offset + args.limit]
    return CatalogOut(products=sliced, total=total)
