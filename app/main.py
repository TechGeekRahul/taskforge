"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import dispose_engine
from app.queue.redis_client import close_redis, get_redis_client

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm infrastructure clients on startup and release them on shutdown."""
    get_redis_client()
    yield
    await close_redis()
    await dispose_engine()


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    debug=settings.debug,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    """Lightweight liveness probe until /health is added in Phase 4."""
    return {
        "service": settings.app_name,
        "version": __version__,
        "status": "ok",
    }
