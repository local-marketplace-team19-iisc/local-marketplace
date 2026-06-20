"""Tools usable in either role."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from backend.agent.schemas import GeoPoint
from backend.agent.tools.base import ToolContext, tool


class Empty(BaseModel):
    pass


class UserProfile(BaseModel):
    user_id: str
    name: str | None = None
    language: str = "en"
    default_location: GeoPoint | None = None


@tool(
    name="get_user_profile",
    input_model=Empty, output_model=UserProfile,
    roles=["vendor", "customer", "unknown"],
    side_effect="read",
    description="Fetch the current user's profile.",
)
async def get_user_profile(_args: Empty, ctx: ToolContext) -> UserProfile:
    # STUB: replace with Postgres lookup.
    return UserProfile(user_id=ctx.user_id or "anon", language="en")


class SetLocationIn(BaseModel):
    lat: float | None = None
    lng: float | None = None
    address: str | None = None


@tool(
    name="set_user_location",
    input_model=SetLocationIn, output_model=GeoPoint,
    roles=["vendor", "customer"],
    side_effect="write",
    description="Persist the user's current location.",
)
async def set_user_location(args: SetLocationIn, ctx: ToolContext) -> GeoPoint:
    # STUB: geocode address if lat/lng missing; persist to DB.
    return GeoPoint(lat=args.lat or 0.0, lng=args.lng or 0.0)


class DistanceIn(BaseModel):
    from_: GeoPoint
    to: GeoPoint


class DistanceOut(BaseModel):
    km: float


@tool(
    name="distance_km",
    input_model=DistanceIn, output_model=DistanceOut,
    roles=["vendor", "customer"],
    side_effect="read",
    description="Great-circle distance between two points.",
)
async def distance_km(args: DistanceIn, _ctx: ToolContext) -> DistanceOut:
    from math import asin, cos, radians, sin, sqrt
    lat1, lon1 = radians(args.from_.lat), radians(args.from_.lng)
    lat2, lon2 = radians(args.to.lat), radians(args.to.lng)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return DistanceOut(km=2 * 6371.0 * asin(sqrt(a)))


class SetLanguageIn(BaseModel):
    lang: str


class Ok(BaseModel):
    ok: bool = True


@tool(
    name="set_language",
    input_model=SetLanguageIn, output_model=Ok,
    roles=["vendor", "customer", "unknown"],
    side_effect="write",
    description="Set the user's preferred language (ISO 639-1).",
)
async def set_language(args: SetLanguageIn, ctx: ToolContext) -> Ok:
    return Ok(ok=True)


class EscalateIn(BaseModel):
    reason: str


class Ticket(BaseModel):
    ticket_id: str
    status: Literal["open"] = "open"


@tool(
    name="escalate_to_human",
    input_model=EscalateIn, output_model=Ticket,
    roles=["vendor", "customer"],
    side_effect="write",
    description="Hand off to a human operator.",
)
async def escalate_to_human(_args: EscalateIn, ctx: ToolContext) -> Ticket:
    return Ticket(ticket_id=f"tkt_{ctx.session_id[-6:]}")
