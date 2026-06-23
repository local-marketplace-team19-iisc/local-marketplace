import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.routes import auth, catalog, health, products
from backend.app.core.config import settings
from backend.app.db.session import Base, engine
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
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(catalog.router, prefix="/api/catalog", tags=["catalog"])


@app.on_event("startup")
def create_003_auth_tables() -> None:
    """Ensure feature 003 auth tables exist for local demos and tests."""
    Base.metadata.create_all(
        bind=engine,
        tables=[User.__table__, Vendor.__table__, RefreshToken.__table__],
    )


_spa_dir = "frontend/build"
_spa_index = os.path.join(_spa_dir, "index.html")

if os.path.exists(_spa_dir):
    app.mount("/", StaticFiles(directory=_spa_dir, html=True), name="frontend")


@app.exception_handler(StarletteHTTPException)
async def spa_fallback(request: Request, exc: StarletteHTTPException) -> FileResponse:
    # For non-API 404s, serve the SPA so React Router handles the path.
    if exc.status_code == 404 and not request.url.path.startswith("/api/") and os.path.exists(_spa_index):
        return FileResponse(_spa_index)
    raise exc


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)


if __name__ == "__main__":
    main()
