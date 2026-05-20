"""FastAPI dependency providers for route handlers."""

from __future__ import annotations

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.queue.redis_client import get_redis
from app.services.task_service import TaskService

__all__ = [
    "get_redis_dep",
    "get_session_dep",
    "get_task_service",
]


async def get_session_dep(
    session: AsyncSession = Depends(get_session),
) -> AsyncSession:
    return session


async def get_redis_dep(redis: Redis = Depends(get_redis)) -> Redis:
    return redis


async def get_task_service(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> TaskService:
    return TaskService(session=session, redis=redis)
