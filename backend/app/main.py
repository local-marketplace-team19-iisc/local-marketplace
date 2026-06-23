import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.agent_router.api import router as agent_route_router
from backend.app.agent_router.chat_adapter import router as agent_chat_router
from backend.app.agent_router.search_adapter import router as agent_search_router
from backend.app.api.routes import auth, catalog, health, orders, products
from backend.app.core.config import settings
from backend.app.db.session import Base, SessionLocal, engine
from backend.app.models.category import Category
from backend.app.models.order import Order
from backend.app.models.order_item import OrderItem
from backend.app.models.product import Product
from backend.app.models.refresh_token import RefreshToken
from backend.app.models.subcategory import SubCategory
from backend.app.models.user import User
from backend.app.models.vendor import Vendor

logger = logging.getLogger(__name__)


def _bootstrap_catalog_tables() -> None:
    """Create + seed the 006 catalog tables on a fresh local DB.

    Production runs Alembic (`make db-migrate`) against Postgres, which creates
    these tables and bulk-inserts the deterministic taxonomy. For local SQLite
    dev there is no migration, so we mirror the migration's create+seed step
    here. Both operations are idempotent:
      * `create_all` is a no-op when the tables already exist.
      * Seeding is gated on `categories` being empty — a second boot does
        nothing.
    """
    Base.metadata.create_all(
        bind=engine,
        tables=[Category.__table__, SubCategory.__table__, Product.__table__],
    )

    from backend.app.catalog.seed_data import iter_categories, iter_subcategories

    db = SessionLocal()
    try:
        if db.query(Category).count() > 0:
            return
        db.add_all(Category(**row) for row in iter_categories())
        db.flush()
        db.add_all(SubCategory(**row) for row in iter_subcategories())
        db.commit()
        logger.info(
            "catalog: seeded %d categories + subcategories on a fresh DB.",
            len(iter_categories()),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Boot-time warm-up.

    1. Ensure feature 003 auth tables exist (sync, cheap, idempotent).
    2. Ensure feature 006 catalog tables exist + are seeded with the
       deterministic taxonomy. Skipped on Postgres deployments where the
       Alembic migration `0004` has already done both.
    3. Best-effort warm the SBERT model + intent index. If the model isn't
       available offline and `ALLOW_MODEL_DOWNLOAD` is false (the CI /
       corporate-firewall default), log a warning and let request-time
       surface the friendly `SBertModelMissingError`.
    """
    Base.metadata.create_all(
        bind=engine,
        tables=[User.__table__, Vendor.__table__, RefreshToken.__table__],
    )
    try:
        _bootstrap_catalog_tables()
    except Exception as e:  # pragma: no cover — defensive; never crash startup
        logger.warning("catalog bootstrap skipped: %s", e)

    # V1 Orders feature — bootstrap on local SQLite the same way the catalog
    # tables are. Production runs Alembic against Postgres; in V1 the orders
    # tables don't have a migration yet, so we mirror create_all here. Order
    # depends on users (003) and OrderItem depends on products + vendors (006),
    # both already created above.
    try:
        Base.metadata.create_all(
            bind=engine,
            tables=[Order.__table__, OrderItem.__table__],
        )
    except Exception as e:  # pragma: no cover — defensive; never crash startup
        logger.warning("orders bootstrap skipped: %s", e)

    try:
        from backend.app.agent_router.intents import get_intent_index
        from backend.app.agent_router.sbert import SBertModelMissingError

        try:
            get_intent_index()
            logger.info("sbert: model and intent index warmed.")
        except SBertModelMissingError as e:
            logger.warning("sbert: %s", e)
    except Exception as e:  # pragma: no cover — defensive; never crash startup
        logger.warning("sbert warmup skipped: %s", e)
    yield


app = FastAPI(
    title="Local Marketplace",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(catalog.router, prefix="/api/catalog", tags=["catalog"])
# /api/orders — V1 customer order placement + history.
# Minimal, deterministic: GET lists the customer's own orders, POST places
# an all-or-nothing multi-vendor order and decrements stock in the same
# transaction. Vendor-side order view is deferred (see backend/app/api/routes/orders.py).
app.include_router(orders.router, tags=["orders"])

# Feature 008 — SBERT lightweight agent router. Three surfaces, one routing core.
# All three call into 006's `product_service` for the actual product CRUD.
app.include_router(agent_route_router, tags=["agent"])
app.include_router(agent_chat_router, tags=["chat"])
app.include_router(agent_search_router, tags=["search"])


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)


if __name__ == "__main__":
    main()
