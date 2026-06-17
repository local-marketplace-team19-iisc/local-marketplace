from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe: is the web server process running?"""
    return {"status": "OK"}
