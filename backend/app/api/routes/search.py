"""Semantic search API routes (feature 008).

Endpoint
--------
POST /api/search  →  200 SearchResponse

Auth
----
No authentication required. Search is a public discovery endpoint so
unauthenticated users (and the NLP chatbot) can browse the catalog before
registering.

Load-time isolation
-------------------
`search_service` (and therefore sqlalchemy.orm, Product, SubCategory …) is
imported LAZILY inside the endpoint body.  This keeps the router module's
own import graph limited to FastAPI, SQLAlchemy Session, and our clean
schemas — none of which carry bcrypt/jose transitive dependencies.
The same lazy-import contract is established by orders.py and is the agreed
pattern for all feature-008+ routes.

Error mapping
-------------
service exception         HTTP status
SearchValidationError  →  422 Unprocessable Entity
SearchError (generic)  →  500 Internal Server Error
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.schemas.search import SearchRequest, SearchResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Shared dependency
# ---------------------------------------------------------------------------

def get_db() -> Session:
    """Yield a database session; close on request teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic product search",
    description=(
        "Accepts a natural language query (e.g. '5 kg sugar', 'something sweet "
        "for tea') and returns relevance-ranked, in-stock products. "
        "Uses bag-of-words TF cosine similarity; the embedding backend is "
        "hot-swappable to sentence-transformers or an OpenAI embeddings call "
        "without any API contract changes. "
        "Products with stock_quantity <= 0 are excluded at the SQL layer "
        "before any scoring is performed."
    ),
    responses={
        200: {"description": "Ranked, in-stock results with pagination envelope."},
        422: {
            "description": (
                "Empty query, whitespace-only input, limit > 50, or negative offset."
            ),
        },
        500: {"description": "Search index failure."},
    },
)
def search_endpoint(
    payload: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    # LAZY IMPORTS — search_service is only resolved at call time, not at
    # module load time.  This enforces the load-time isolation constraint from
    # spec.md: no heavy or cryptographic transitive dependencies are pulled
    # into sys.modules simply because this router was registered in main.py.
    from backend.app.services.search_service import (
        SearchError,
        SearchValidationError,
        search_products,
    )

    try:
        return search_products(
            db,
            query=payload.q,
            limit=payload.limit,
            offset=payload.offset,
        )
    except SearchValidationError as exc:
        # query was empty / whitespace after strip — should be caught by Pydantic
        # first, but the service layer provides a second validation fence.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except SearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
