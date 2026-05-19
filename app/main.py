"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app import __version__
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    debug=settings.debug,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    """Lightweight liveness probe until /health is added in Phase 4."""
    return {
        "service": settings.app_name,
        "version": __version__,
        "status": "ok",
    }
