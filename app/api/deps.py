"""FastAPI dependency providers for route handlers."""

from __future__ import annotations

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.queue.redis_client import get_redis
from app.services.task_service import TaskService


async def get_task_service(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> TaskService:
    return TaskService(session=session, redis=redis)
