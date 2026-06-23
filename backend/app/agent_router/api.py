"""`POST /api/agent/route` — verbose one-shot intent-router endpoint (spec FR-6).

Wire shape:
    Request:
        {
            "text": "Show me iPhone 15 under ₹60,000",
            "role": "customer"     # optional override; defaults from JWT
        }
    Response:
        {
            "intent": "search_products",
            "entities": {"keywords": "iphone 15", "max_price": 60000.0, ...},
            "reply": "Found 1 match.",
            "listings": [{"id": ..., "name": ..., "price": ..., ...}],
            "api_called": "GET /api/products",
            "api_status": 200,
            "meta": {}
        }

This endpoint requires a Bearer token (FR-6). Anonymous search lives at
`/api/search` instead — different endpoint, different auth posture.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.app.agent_router import route as router_logic
from backend.app.agent_router._auth import require_principal, role_and_vendor
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentRouteBody(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    text: str = Field(min_length=1, description="Natural-language utterance (text or voice-transcribed).")
    role: Optional[str] = Field(
        default=None,
        description=(
            "Optional override. If omitted, the user_type from the JWT is "
            "used. Useful for testing the router from a privileged tool."
        ),
    )


class AgentRouteReply(BaseModel):
    intent: str
    entities: dict[str, Any] = Field(default_factory=dict)
    reply: str
    listings: list[dict[str, Any]] = Field(default_factory=list)
    api_called: Optional[str] = None
    api_status: int = 200
    meta: dict[str, Any] = Field(default_factory=dict)


@router.post("/api/agent/route", response_model=AgentRouteReply)
async def agent_route(body: AgentRouteBody, request: Request) -> AgentRouteReply:
    principal = require_principal(request)
    jwt_role, vendor_id = role_and_vendor(principal)
    effective_role = (body.role or jwt_role) if body.role in {"customer", "vendor", "unknown"} else jwt_role

    # The router itself is CPU-bound (SBERT encode + dict lookups). Run it in
    # the default threadpool so FastAPI's event loop stays responsive under
    # parallel requests; this is the same trick `run_in_executor`/`to_thread`
    # gives us in feature 002.
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                router_logic.route_text, body.text, effective_role, vendor_id
            ),
            timeout=float(settings.AGENT_CHAT_TURN_TIMEOUT_S),
        )
    except asyncio.TimeoutError as e:
        logger.warning(
            "agent_route_timeout user_id=%s text=%r",
            principal.get("id"),
            body.text[:80],
        )
        raise HTTPException(status_code=504, detail="Agent router timed out.") from e

    return AgentRouteReply(
        intent=result.intent,
        entities=result.entities,
        reply=result.reply,
        listings=result.listings,
        api_called=result.api_called,
        api_status=result.api_status,
        meta=result.meta,
    )
