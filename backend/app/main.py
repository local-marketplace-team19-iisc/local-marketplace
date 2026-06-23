from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import auth, catalog, health, orders, products
from backend.app.core.config import settings
from backend.app.db.session import Base, engine
from backend.app.models.order import Cart, CartItem, Order, OrderItem
from backend.app.models.refresh_token import RefreshToken
from backend.app.models.user import User
from backend.app.models.vendor import Vendor

app = FastAPI(
    title="Local Marketplace",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])


@app.on_event("startup")
def create_tables() -> None:
    """Ensure all feature tables exist for local demos and tests.

    Production uses Alembic migrations; this handler covers the SQLite
    fallback path so `make dev` works without a Postgres connection.
    """
    Base.metadata.create_all(
        bind=engine,
        tables=[
            # feature 003 — auth
            User.__table__,
            Vendor.__table__,
            RefreshToken.__table__,
            # feature 007 — cart & orders
            Cart.__table__,
            CartItem.__table__,
            Order.__table__,
            OrderItem.__table__,
        ],
    )


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)


if __name__ == "__main__":
    main()
