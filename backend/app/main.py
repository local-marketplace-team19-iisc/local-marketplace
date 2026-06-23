from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import auth, health
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
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


@app.on_event("startup")
def create_003_auth_tables() -> None:
    """Ensure feature 003 auth tables exist for local demos and tests."""
    Base.metadata.create_all(
        bind=engine,
        tables=[User.__table__, Vendor.__table__, RefreshToken.__table__],
    )


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)


if __name__ == "__main__":
    main()
