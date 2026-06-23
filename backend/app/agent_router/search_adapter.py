"""`GET /api/search?q=…` — search-bar adapter on top of the SBERT router (FR-8).

The frontend's `searchService.searchProducts(query)` already calls this URL
(it was mocked before this feature). The adapter forces the router intent
to `search_products` — there is no need to classify a search-bar query, by
contract.

Response shape matches the frontend's existing `productContext` consumer:
    { "products": [<Listing>, ...] }
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.app.agent_router import route as router_logic
from backend.app.agent_router._auth import optional_principal, role_and_vendor
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class SearchReply(BaseModel):
    products: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


@router.get("/api/search", response_model=SearchReply)
async def search(
    request: Request,
    q: str = Query(default="", description="Natural-language search query."),
) -> SearchReply:
    """Anonymous-friendly NL search. Forces intent=search_products."""
    principal = optional_principal(request)
    role, vendor_id = role_and_vendor(principal)
    # `optional_principal` returns "unknown" role for anonymous; that's still
    # allowed to search per spec FR-4.
    if role not in {"customer", "vendor", "unknown"}:
        role = "unknown"

    text = (q or "").strip()
    if not text:
        return SearchReply(products=[], meta={"empty_query": True})

    # Skip classification — the search bar query is *defined* to be a search.
    # `forced_intent` lets us reuse the router's q/price/listings logic
    # without paying the SBERT-encode cost on every search-bar keystroke.
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                router_logic.route_text,
                text,
                role,
                vendor_id,
                forced_intent="search_products",
            ),
            timeout=float(settings.AGENT_CHAT_TURN_TIMEOUT_S),
        )
    except asyncio.TimeoutError as e:
        raise HTTPException(status_code=504, detail="Search router timed out.") from e

    return SearchReply(
        products=result.listings,
        meta={
            "keywords": result.entities.get("keywords"),
            "max_price": result.entities.get("max_price"),
            "min_price": result.entities.get("min_price"),
            **(result.meta or {}),
        },
    )
