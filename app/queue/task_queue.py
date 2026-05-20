"""Redis list queue for pending task jobs."""

from __future__ import annotations

import time
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

    def __init__(
        self,
        redis: Redis,
        queue_key: str,
        retry_queue_key: str,
    ) -> None:
        self._redis = redis
        self._queue_key = queue_key
        self._retry_queue_key = retry_queue_key

    @classmethod
    def from_settings(cls, redis: Redis, settings: Settings | None = None) -> TaskQueue:
        cfg = settings or get_settings()
        return cls(
            redis=redis,
            queue_key=cfg.task_queue_key,
            retry_queue_key=cfg.task_retry_queue_key,
        )

    async def enqueue(self, message: TaskQueueMessage) -> int:
        """
        Push a task onto the queue head.

        Returns the new length of the list after push.
        """
        payload = message.model_dump_json()
        return int(await self._redis.lpush(self._queue_key, payload))

    async def dequeue(self, timeout: int = 5) -> TaskQueueMessage | None:
        """
        Block until a message is available, then return it.

        ``timeout`` is seconds to wait before returning None (worker idle poll).
        BRPOP on the list tail pairs with LPUSH on the head (FIFO).
        """
        result = await self._redis.brpop(self._queue_key, timeout=timeout)
        if result is None:
            return None
        _key, raw_payload = result
        return TaskQueueMessage.model_validate_json(raw_payload)

    async def enqueue_delayed(
        self,
        message: TaskQueueMessage,
        delay_seconds: float,
    ) -> None:
        """Schedule a message for re-delivery after ``delay_seconds`` (exponential backoff)."""
        run_at = time.time() + max(0.0, delay_seconds)
        payload = message.model_dump_json()
        await self._redis.zadd(self._retry_queue_key, {payload: run_at})

    async def release_due_retries(self) -> int:
        """
        Move due delayed messages onto the main queue.

        Returns the number of messages released.
        """
        now = time.time()
        due = await self._redis.zrangebyscore(self._retry_queue_key, "-inf", now)
        if not due:
            return 0

        async with self._redis.pipeline(transaction=True) as pipe:
            for raw_payload in due:
                pipe.zrem(self._retry_queue_key, raw_payload)
                pipe.lpush(self._queue_key, raw_payload)
            await pipe.execute()

        return len(due)

    async def depth(self) -> int:
        """Current number of messages waiting in the queue."""
        return int(await self._redis.llen(self._queue_key))

    async def retry_depth(self) -> int:
        """Number of messages waiting in the delayed retry schedule."""
        return int(await self._redis.zcard(self._retry_queue_key))
