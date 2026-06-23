"""Semantic product search service (feature 008).

Embedding strategy
------------------
Vectors are sparse, L2-normalised term-frequency (TF) maps built from Python
stdlib alone (re, math, collections.Counter).  No sentence-transformers,
numpy, or any external ML library is required at load time.

The `_embed` / `_cosine` interface is deliberately narrow so that a future
sprint can hot-swap the embedding backend (e.g. sentence-transformers or an
OpenAI embeddings call) without touching the service contract or any tests:
only `_embed` needs to change.

Stock enforcement
-----------------
`Product.stock_quantity > 0` is applied as a SQL WHERE clause BEFORE any
scoring is computed.  Post-filtering would corrupt the `total` count in the
pagination envelope and waste memory loading unsellable rows.

N+1 prevention
--------------
`joinedload(Product.subcategory).joinedload(SubCategory.category)` and
`joinedload(Product.vendor)` load the entire relationship graph in a single
query, avoiding one extra SELECT per product.
"""

import math
import re
from collections import Counter

from sqlalchemy.orm import Session, joinedload

from backend.app.models.product import Product
from backend.app.models.subcategory import SubCategory
from backend.app.schemas.search import (
    ProductSearchItem,
    SearchResponse,
    VendorSearchDetail,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SearchError(Exception):
    """Base error for all search operations."""


class SearchValidationError(SearchError):
    """Raised for invalid search inputs (empty query, bad pagination, etc.)."""


# ---------------------------------------------------------------------------
# Embedding engine  (stdlib-only, zero load-time deps)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Extract lowercase alphanumeric tokens; discard punctuation and spaces."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _embed(text: str) -> dict[str, float]:
    """Build a sparse, L2-normalised term-frequency vector.

    Returns a dict mapping each token to its normalised frequency weight.
    An empty text or text with no alphanumeric tokens returns an empty dict.
    The returned vector is a unit vector (||v|| = 1.0) so the dot product with
    any other unit vector is the cosine similarity.
    """
    tokens = _tokenize(text)
    if not tokens:
        return {}
    counts: dict[str, int] = Counter(tokens)
    magnitude = math.sqrt(sum(freq * freq for freq in counts.values()))
    if magnitude == 0.0:
        return {}
    return {term: freq / magnitude for term, freq in counts.items()}


def _cosine(query_vec: dict[str, float], product_vec: dict[str, float]) -> float:
    """Dot product of two sparse unit vectors — equals cosine similarity.

    Iterates over the query vector (typically shorter) for O(|query_tokens|)
    complexity rather than O(|product_tokens|).  Result is in [0.0, 1.0].
    """
    if not query_vec or not product_vec:
        return 0.0
    return sum(weight * product_vec.get(term, 0.0) for term, weight in query_vec.items())


# ---------------------------------------------------------------------------
# Corpus builder
# ---------------------------------------------------------------------------

def _product_corpus(product: Product) -> str:
    """Concatenate all searchable text fields for a product into one string.

    Includes category/subcategory names if the relationship was eagerly loaded,
    which gives the embedding richer semantic signal (e.g. a query for "dairy"
    will match a milk product even if the word "dairy" isn't in its description).
    """
    parts: list[str] = [
        product.product_name,
        product.brand,
        product.description,
        product.unit_type,
    ]
    if product.subcategory:
        parts.append(product.subcategory.subcategory_name)
        if product.subcategory.category:
            parts.append(product.subcategory.category.category_name)
    return " ".join(filter(None, parts))


# ---------------------------------------------------------------------------
# Result mapper
# ---------------------------------------------------------------------------

def _to_search_item(score: float, product: Product) -> ProductSearchItem:
    """Convert a (score, Product ORM) pair into a ProductSearchItem schema."""
    vendor = product.vendor
    vendor_detail: VendorSearchDetail | None = None
    if vendor:
        vendor_detail = VendorSearchDetail(
            vendor_id=str(vendor.id),
            shop_name=vendor.shop_name,
            shop_location_lat=float(vendor.shop_location_lat),
            shop_location_lon=float(vendor.shop_location_lon),
            shop_description=vendor.shop_description,
        )

    subcategory_name = ""
    category_name = ""
    if product.subcategory:
        subcategory_name = product.subcategory.subcategory_name
        if product.subcategory.category:
            category_name = product.subcategory.category.category_name

    return ProductSearchItem(
        product_id=str(product.product_id),
        product_name=product.product_name,
        brand=product.brand,
        description=product.description,
        price_inr=float(product.price_inr),
        stock_quantity=product.stock_quantity,
        unit_type=str(product.unit_type),
        unit_value=float(product.unit_value),
        vendor_id=str(product.vendor_id),
        vendor=vendor_detail,
        category=category_name,
        subcategory=subcategory_name,
        relevance_score=round(min(score, 1.0), 6),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_products(
    db: Session,
    query: str,
    limit: int = 10,
    offset: int = 0,
) -> SearchResponse:
    """Execute a semantic search over in-stock products.

    Pipeline
    --------
    1. Strip and validate the query string.
    2. SQL WHERE stock_quantity > 0  — hard inventory gate before any scoring.
    3. Eagerly load subcategory → category and vendor in a single query.
    4. Compute cosine similarity between the query vector and each product corpus.
    5. Discard zero-similarity products (no token overlap with the query).
    6. Sort descending by score, paginate, return SearchResponse.

    Args:
        db:     Active SQLAlchemy Session.
        query:  Raw natural language query string.
        limit:  Max items per page (1–50).
        offset: Zero-based page start index.

    Returns:
        SearchResponse with ranked, in-stock results and pagination metadata.

    Raises:
        SearchValidationError: query is empty or whitespace-only after stripping.
        SearchError:           unexpected persistence failure.
    """
    clean_query = query.strip()
    if not clean_query:
        raise SearchValidationError(
            "Query must not be empty or contain only whitespace characters."
        )

    try:
        # ------------------------------------------------------------------ #
        # 1. Fetch only in-stock products — SQL filter runs before Python code.
        #    joinedload collapses subcategory→category and vendor into one query,
        #    eliminating N+1 SELECT patterns.
        # ------------------------------------------------------------------ #
        products: list[Product] = (
            db.query(Product)
            .filter(Product.stock_quantity > 0)
            .options(
                joinedload(Product.subcategory).joinedload(SubCategory.category),
                joinedload(Product.vendor),
            )
            .all()
        )

        # ------------------------------------------------------------------ #
        # 2. Embed the query once; compare against each product corpus.
        # ------------------------------------------------------------------ #
        query_vec = _embed(clean_query)

        scored: list[tuple[float, Product]] = []
        for product in products:
            score = _cosine(query_vec, _embed(_product_corpus(product)))
            if score > 0.0:                # discard products with no token overlap
                scored.append((score, product))

        # ------------------------------------------------------------------ #
        # 3. Sort descending by relevance, paginate.
        # ------------------------------------------------------------------ #
        scored.sort(key=lambda pair: pair[0], reverse=True)

        total = len(scored)
        page = scored[offset : offset + limit]

        results = [_to_search_item(score, product) for score, product in page]

    except SearchError:
        raise
    except Exception as exc:
        raise SearchError(f"Search failed unexpectedly: {exc}") from exc

    return SearchResponse(
        query=clean_query,
        total=total,
        limit=limit,
        offset=offset,
        results=results,
    )
