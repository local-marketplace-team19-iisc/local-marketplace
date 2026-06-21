from fastapi import FastAPI

from backend.app.api.routes import auth, health
from backend.app.core.config import settings

app = FastAPI(
    title="Local Marketplace",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)


if __name__ == "__main__":
    main()
