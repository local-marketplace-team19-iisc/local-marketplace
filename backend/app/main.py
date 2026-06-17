from fastapi import FastAPI

from backend.app.api.routes import health
from backend.app.core.config import settings

# Auto-docs (/docs, /redoc, /openapi.json) disabled so that /health is the only
# route — SPEC §7 "No route other than /health exists".
app = FastAPI(
    title="Local Marketplace",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(health.router)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)


if __name__ == "__main__":
    main()
