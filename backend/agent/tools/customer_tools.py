"""Customer-only tools (baseline).

Baseline scope:
- `search_products` — reads from the in-memory store, simple keyword match,
  optional price + unit filter, sorted by score then distance. No vector
  retrieval, no LTR; those move in later (`spec.md §5.6`).
- `get_store` — fetch a store by id (for the "view 1" follow-up turn).

Deferred to a later round (NOT registered):
- `add_to_cart`, `place_order`, `cancel_order`, `get_my_history`.
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from pydantic import BaseModel

from backend.agent.schemas import GeoPoint, RankedProduct, SearchQuery, Store
from backend.agent.tools import _store
from backend.agent.tools.base import ToolContext, tool


# --------------------------------------------------------------------------- #
# search_products
# --------------------------------------------------------------------------- #


class SearchOut(BaseModel):
    results: list[RankedProduct] = []


def _haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    lat1, lon1 = radians(a.lat), radians(a.lng)
    lat2, lon2 = radians(b.lat), radians(b.lng)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def _keyword_score(query: str, name: str, category: str) -> float:
    """Tiny keyword-overlap score in [0, 1]. Good enough for the baseline.

    Splits on whitespace, lowercases, intersects token sets. A real search
    layer (`spec.md §5.6`) will swap this for BM25 + vector + reranker.
    """
    q_tokens = {t for t in query.lower().split() if len(t) > 1}
    if not q_tokens:
        return 0.0
    haystack_tokens = set(name.lower().split()) | set(category.lower().split())
    overlap = q_tokens & haystack_tokens
    if not overlap:
        return 0.0
    return len(overlap) / len(q_tokens)


@tool(
    name="search_products",
    input_model=SearchQuery,
    output_model=SearchOut,
    roles=["customer"],
    side_effect="read",
    description=(
        "Search the in-memory product catalog. Baseline: keyword overlap "
        "score with optional unit / max_price filters; sorted by score "
        "descending, then distance ascending."
    ),
)
async def search_products(args: SearchQuery, ctx: ToolContext) -> SearchOut:
    cfg = ctx.config
    return_top_k = int(getattr(cfg.retrieval, "return_top_k", 5))
    # Use the search's `near` if provided, else fall back to a hard-coded
    # Bangalore centroid. Session-location plumbing is a later round.
    origin = args.near or GeoPoint(lat=12.9716, lng=77.5946)

    candidates: list[RankedProduct] = []
    for p in _store.iter_products():
        if not p.availability:
            continue
        if args.unit and p.unit != args.unit:
            continue
        if args.max_price is not None and p.price > args.max_price:
            continue
        score = _keyword_score(args.text, p.name, p.category)
        if score <= 0.0:
            continue
        store = _store.get_store(p.store_id)
        store_geo = GeoPoint(lat=store.lat, lng=store.lng) if store else origin
        distance_km = _haversine_km(origin, store_geo)
        if distance_km > float(args.radius_km):
            continue
        candidates.append(
            RankedProduct(
                product_id=p.product_id,
                store_id=p.store_id,
                name=p.name,
                price=p.price,
                unit=p.unit,
                quantity_available=p.quantity,
                distance_km=round(distance_km, 2),
                rating=store.rating if store else 0.0,
                eta_min=int(round(distance_km * 6)),  # ~10 km/h delivery proxy
                score=round(score, 3),
            )
        )

    candidates.sort(key=lambda r: (-r.score, r.distance_km))
    return SearchOut(results=candidates[:return_top_k])


# --------------------------------------------------------------------------- #
# get_store
# --------------------------------------------------------------------------- #


class GetStoreIn(BaseModel):
    store_id: str


@tool(
    name="get_store",
    input_model=GetStoreIn,
    output_model=Store,
    roles=["customer", "vendor"],
    side_effect="read",
    description="Fetch a store's public details by id.",
)
async def get_store(args: GetStoreIn, _ctx: ToolContext) -> Store:
    store = _store.get_store(args.store_id)
    if store is None:
        raise ValueError(f"unknown store_id: {args.store_id}")
    return store
