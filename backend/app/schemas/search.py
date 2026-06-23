"""Pydantic request/response schemas for the semantic search API (feature 008).

All validation runs at the API gateway layer before any service logic is invoked,
satisfying the spec constraint on input validation bounds.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    """POST /api/search — request body.

    The `q` validator strips surrounding whitespace THEN checks that the
    result is non-empty, so a query like "   " (spaces only) is blocked
    before it reaches the embedding pipeline.  `min_length=1` alone would
    not catch this because Pydantic measures length before stripping.
    """

    model_config = ConfigDict(str_strip_whitespace=False)  # we handle stripping ourselves

    q: str = Field(
        min_length=1,
        description="Natural language product search query (e.g. '5 kg sugar').",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum results per page (1–50).",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Zero-based result offset for pagination.",
    )

    @field_validator("q")
    @classmethod
    def _q_must_not_be_whitespace_only(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError(
                "Query must not be empty or contain only whitespace characters."
            )
        return stripped  # downstream consumers receive the cleaned value


# ---------------------------------------------------------------------------
# Response building blocks
# ---------------------------------------------------------------------------

class VendorSearchDetail(BaseModel):
    """Minimal vendor context embedded in each search result.

    Lets the frontend render distance / shop info without a second round-trip.
    """

    vendor_id: str
    shop_name: str
    shop_location_lat: float
    shop_location_lon: float
    shop_description: Optional[str] = None


class ProductSearchItem(BaseModel):
    """A single ranked product entry in the search response.

    `relevance_score` is the cosine similarity between the query vector and the
    product corpus vector (range 0.0–1.0, higher = more relevant).
    `category` and `subcategory` are resolved from the ORM relationship chain
    at query time, so the frontend never needs to make a separate catalog call.
    """

    product_id: str
    product_name: str
    brand: str
    description: str
    price_inr: float
    stock_quantity: int
    unit_type: str
    unit_value: float
    vendor_id: str
    vendor: Optional[VendorSearchDetail] = None
    category: str
    subcategory: str
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalised cosine similarity score (0.0–1.0).",
    )


# ---------------------------------------------------------------------------
# Paginated envelope
# ---------------------------------------------------------------------------

class SearchResponse(BaseModel):
    """200 OK — paginated, relevance-ranked search results.

    `total` reflects the count of *in-stock* matches BEFORE pagination, so the
    client can compute page counts correctly.
    `query` echoes back the cleaned (stripped) query string.
    """

    query: str = Field(description="The cleaned query string that was searched.")
    total: int = Field(ge=0, description="Total matching in-stock products (pre-pagination).")
    limit: int = Field(ge=1, le=50)
    offset: int = Field(ge=0)
    results: list[ProductSearchItem]
