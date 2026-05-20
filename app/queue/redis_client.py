"""Shared async Redis client for dependency injection."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency: yields the process-wide Redis client."""
    yield get_redis_client()


def get_redis_client() -> Redis:
    """Return a lazily initialized Redis client (decode_responses=True)."""
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(
            str(settings.redis_url),
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    """Close Redis connection and reset singleton (shutdown and tests)."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None
