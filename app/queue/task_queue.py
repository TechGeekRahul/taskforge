"""Redis list queue for pending task jobs."""

from __future__ import annotations

import json
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict
from redis.asyncio import Redis

from app.core.config import Settings, get_settings


class TaskQueueMessage(BaseModel):
    """Payload pushed to Redis for workers to dequeue."""

    model_config = ConfigDict(extra="forbid")

    task_id: uuid.UUID
    task_type: str
    payload: dict[str, Any] | None = None


class TaskQueue:
    """LPUSH/BRPOP-style FIFO queue backed by a Redis list."""

    def __init__(self, redis: Redis, queue_key: str) -> None:
        self._redis = redis
        self._queue_key = queue_key

    @classmethod
    def from_settings(cls, redis: Redis, settings: Settings | None = None) -> TaskQueue:
        cfg = settings or get_settings()
        return cls(redis=redis, queue_key=cfg.task_queue_key)

    async def enqueue(self, message: TaskQueueMessage) -> int:
        """
        Push a task onto the queue head.

        Returns the new length of the list after push.
        """
        payload = message.model_dump_json()
        return int(await self._redis.lpush(self._queue_key, payload))

    async def depth(self) -> int:
        """Current number of messages waiting in the queue."""
        return int(await self._redis.llen(self._queue_key))
