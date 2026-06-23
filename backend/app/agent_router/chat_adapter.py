"""`POST /api/chat` — chatbot adapter on top of the SBERT router (spec FR-7).

This is the **replacement** for feature 007's planner-backed `/api/chat`.
The request and response wire shapes are preserved byte-for-byte so the
frontend chatbot UI (feature 004) does not change. Internally, instead of
calling feature 002's `Orchestrator.handle_turn(...)`, we call
`router_logic.route_text(...)` — stateless, no Redis, no planner.

Differences from feature 007's contract that frontend code might notice:
  * `sessionId` is *echoed back* but never read server-side. The router is
    stateless; if the frontend wants conversational memory, that's a future
    feature.
  * Image uploads are still on hold (feature 007 FR-6 carries over). A
    multipart with image-only payload returns a polite deferral reply with
    no `listings` and the planner is *not* invoked.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from backend.app.agent_router import route as router_logic
from backend.app.agent_router._auth import require_principal, role_and_vendor
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


_ALLOWED_FORCED_INTENTS = frozenset({
    "search_products",
    "add_product",
    "update_product",
    "delete_product",
    "get_my_listings",
    "get_categories",
})


class ChatBody(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    message: str = Field(default="")
    sessionId: str | None = None
    # Optional intent hint from the caller. When set, SBERT classification
    # is **skipped** and the router executes the named intent directly
    # (spec FR-7a, session 9). Surfaces like the Add Product modal use this
    # because they are *defined* to be `add_product` — letting SBERT
    # classify free-form descriptions like "Amul butter 100g, ₹58" risks
    # misclassification as `search_products`. The chatbot UI (where intent
    # is genuinely ambiguous) continues to omit this field. Unknown values
    # are silently ignored so old clients don't break.
    intent: str | None = None


class ChatListing(BaseModel):
    """Frontend-shaped product card (spec FR-10)."""

    id: str
    name: str
    price: float
    vendor: str = ""
    rating: float = 0.0
    availability: bool = True


class ChatDebug(BaseModel):
    """SBERT classifier telemetry — useful for chatbot 'how did it decide?' UI.

    Optional; the chatbot can render a small badge like
    `[add_product · 0.89]` next to assistant replies. Frontend MUST tolerate
    its absence (older deployments don't include it).
    """

    intent: str
    confidence: float


class ChatReply(BaseModel):
    reply: str
    listings: list[ChatListing] = Field(default_factory=list)
    sessionId: str
    debug: ChatDebug | None = None


def _mint_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:12]}"


async def _read_json(request: Request) -> dict[str, Any]:
    try:
        return await request.json()
    except Exception:
        return {}


@router.post("/api/chat", response_model=ChatReply)
async def chat(
    request: Request,
    message: str | None = Form(default=None),
    sessionId: str | None = Form(default=None),
    intent: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
) -> ChatReply:
    principal = require_principal(request)
    role, vendor_id = role_and_vendor(principal)

    # Adapt the inbound wire shape. Multipart (when present) wins because
    # that's what voice/image flows use; otherwise JSON.
    if message is None and image is None:
        body_dict = await _read_json(request)
        body = ChatBody(**body_dict) if body_dict else ChatBody()
    else:
        body = ChatBody(message=message or "", sessionId=sessionId, intent=intent)

    text = (body.message or "").strip()

    # Image-on-hold path — polite deferral, no router invocation.
    if image is not None and not text:
        return ChatReply(
            reply=(
                "Image search is coming in a future update — "
                "please type or speak your question for now."
            ),
            listings=[],
            sessionId=body.sessionId or _mint_session_id(),
        )

    if not text:
        return ChatReply(
            reply="Tell me what you're looking for and I'll find nearby options.",
            listings=[],
            sessionId=body.sessionId or _mint_session_id(),
        )

    session_id = body.sessionId or _mint_session_id()

    # Validate `intent` hint server-side: only allow our known intents,
    # otherwise drop it silently so we fall back to SBERT classification.
    forced_intent = (
        body.intent
        if body.intent and body.intent in _ALLOWED_FORCED_INTENTS
        else None
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                router_logic.route_text,
                text,
                role,
                vendor_id,
                forced_intent=forced_intent,
            ),
            timeout=float(settings.AGENT_CHAT_TURN_TIMEOUT_S),
        )
    except asyncio.TimeoutError:
        logger.warning(
            "chat_turn_timeout user_id=%s session_id=%s",
            principal.get("id"),
            session_id,
        )
        return ChatReply(
            reply="That took longer than expected — please try again.",
            listings=[],
            sessionId=session_id,
        )

    return ChatReply(
        reply=result.reply,
        listings=[ChatListing(**lst) for lst in result.listings],
        sessionId=session_id,
        debug=ChatDebug(intent=result.intent, confidence=result.confidence),
    )
