"""Pydantic models for every cross-boundary object the agent touches.

Treat every model here as a *contract*:
- LLM tool arguments are validated against the `*In` models before execution.
- Tool return values are validated against the `*Out` models before being
  shown to the planner. This keeps the LLM from leaking malformed data
  back into the conversation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

Role = Literal["vendor", "customer", "unknown"]
Channel = Literal["web", "whatsapp", "voice", "mobile"]
Modality = Literal["text", "voice", "image", "text+image"]
Unit = Literal["kg", "g", "l", "ml", "pcs", "pack"]
Currency = Literal["INR", "USD"]


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)


class Attachment(BaseModel):
    kind: Literal["image", "audio", "location"]
    url: str | None = None
    embedding: list[float] | None = None


class Message(BaseModel):
    """Canonical user-or-assistant message after channel decoding."""
    text: str = Field(min_length=0, max_length=4096)
    language: str = "en"
    modality: Modality = "text"
    attachments: list[Attachment] = Field(default_factory=list)
    geo: GeoPoint | None = None


# ---------------------------------------------------------------------------
# Catalog domain
# ---------------------------------------------------------------------------

class ProductDraft(BaseModel):
    """Output of `extract_product_fields` — never written to DB without
    explicit user confirmation."""
    name: str = Field(min_length=1, max_length=200)
    brand: str | None = None
    category: str = Field(min_length=1, max_length=120)
    price: float = Field(gt=0)
    currency: Currency = "INR"
    quantity: float = Field(gt=0)
    unit: Unit
    availability: bool = True
    location: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    needs_clarification: list[str] = Field(default_factory=list)


class Product(ProductDraft):
    product_id: str
    store_id: str
    created_at: datetime
    updated_at: datetime


class Store(BaseModel):
    store_id: str
    vendor_id: str
    name: str
    category: str
    region: str
    lat: float
    lng: float
    rating: float = 0.0


class Vendor(BaseModel):
    vendor_id: str
    phone: str
    name: str
    kyc_status: Literal["pending", "verified", "rejected"] = "pending"


# ---------------------------------------------------------------------------
# Search & commerce
# ---------------------------------------------------------------------------

class SearchQuery(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    quantity: float | None = Field(default=None, gt=0)
    unit: Unit | None = None
    max_price: float | None = Field(default=None, gt=0)
    near: GeoPoint | None = None
    radius_km: float = Field(default=5.0, gt=0, le=25.0)
    sort_by: Literal["best", "price", "distance", "rating"] = "best"


class RankedProduct(BaseModel):
    product_id: str
    store_id: str
    name: str
    price: float
    unit: Unit
    quantity_available: float
    distance_km: float
    rating: float
    eta_min: int
    score: float


class Cart(BaseModel):
    cart_id: str
    customer_id: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: float = 0.0


class Order(BaseModel):
    order_id: str
    customer_id: str
    store_id: str
    items: list[dict[str, Any]]
    status: Literal["pending", "confirmed", "delivered", "cancelled"] = "pending"
    total: float
    placed_at: datetime


# ---------------------------------------------------------------------------
# Planner I/O
# ---------------------------------------------------------------------------

class ToolCall(BaseModel):
    """A single tool invocation requested by the planner."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _tool_name_charset(cls, v: str) -> str:
        if not v.replace("_", "").isalnum():
            raise ValueError("tool name must be snake_case alnum")
        return v


class PlannerOutput(BaseModel):
    """The structured JSON the LLM must emit at every turn."""
    model_config = ConfigDict(extra="forbid")

    thought: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=4)
    assistant: str = ""


class ToolResult(BaseModel):
    """What the orchestrator feeds back into the planner after a tool runs."""
    name: str
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: int = 0


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class PendingAction(BaseModel):
    """An action that has been previewed to the user and is awaiting 'yes'."""
    tool_name: str
    args: dict[str, Any]
    created_at: datetime


class TokenUsage(BaseModel):
    prompt: int = 0
    completion: int = 0
    cost_usd: float = 0.0


class Turn(BaseModel):
    turn_id: str
    user_msg: Message
    intent: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    assistant_msg: Message | None = None
    latency_ms: int = 0
    tokens: TokenUsage = Field(default_factory=TokenUsage)


class Session(BaseModel):
    session_id: str
    user_id: str | None = None
    role: Role = "unknown"
    channel: Channel = "web"
    language: str = "en"
    location: GeoPoint | None = None
    turns: list[Turn] = Field(default_factory=list)
    summary: str = ""
    pending_action: PendingAction | None = None
    created_at: datetime
    last_active_at: datetime


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------

class TurnRequest(BaseModel):
    session_id: str | None = None
    user_id: str | None = None
    channel: Channel = "web"
    input: Message


class TurnResponse(BaseModel):
    session_id: str
    turn_id: str
    assistant: str
    ui_blocks: list[dict[str, Any]] = Field(default_factory=list)
    pending_action: PendingAction | None = None
    latency_ms: int
