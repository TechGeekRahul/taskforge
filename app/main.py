"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import __version__
from app.api.router import v1_router
from app.api.routes import health, metrics
from app.api.routes.tasks import limiter
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import dispose_engine
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.queue.redis_client import close_redis, get_redis_client

settings = get_settings()
setup_logging(settings.log_level)


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

limiter.enabled = settings.rate_limit_enabled
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(v1_router)
app.include_router(health.router)
app.include_router(metrics.router)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    """Service metadata."""
    return {
        "service": settings.app_name,
        "version": __version__,
        "status": "ok",
        "api": "/api/v1",
    }
