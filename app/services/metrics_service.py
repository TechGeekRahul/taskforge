"""Aggregate operational metrics for JSON /metrics."""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task import Task
from app.observability import prometheus as prom
from app.queue.task_queue import TaskQueue


@dataclass(frozen=True)
class MetricsSnapshot:
    queue_depth: int
    retry_queue_depth: int
    dlq_depth: int
    tasks_by_status: dict[str, int]
    success_rate: float | None
    worker_heartbeat: str | None

    def to_dict(self) -> dict:
        return {
            "queue_depth": self.queue_depth,
            "retry_queue_depth": self.retry_queue_depth,
            "dlq_depth": self.dlq_depth,
            "tasks_by_status": self.tasks_by_status,
            "success_rate": self.success_rate,
            "worker_heartbeat": self.worker_heartbeat,
        }


class MetricsService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis
        self._queue = TaskQueue.from_settings(redis)

    async def snapshot(self) -> MetricsSnapshot:
        main_depth = await self._queue.depth()
        retry_depth = await self._queue.retry_depth()
        dlq_depth = await self._queue.dlq_depth()
        prom.set_queue_depths(main_depth, retry_depth, dlq_depth)

        rows = await self._session.execute(
            select(Task.status, func.count()).group_by(Task.status),
        )
        tasks_by_status = {
            status.value if isinstance(status, TaskStatus) else str(status): count
            for status, count in rows.all()
        }

        completed = tasks_by_status.get(TaskStatus.COMPLETED.value, 0)
        terminal_failed = (
            tasks_by_status.get(TaskStatus.DEAD_LETTER.value, 0)
            + tasks_by_status.get(TaskStatus.FAILED.value, 0)
        )
        terminal_total = completed + terminal_failed
        success_rate = (completed / terminal_total) if terminal_total > 0 else None

        from app.core.config import get_settings

        settings = get_settings()
        heartbeat = await self._redis.get(settings.worker_heartbeat_key)
        worker_heartbeat = heartbeat if isinstance(heartbeat, str) else None

        return MetricsSnapshot(
            queue_depth=main_depth,
            retry_queue_depth=retry_depth,
            dlq_depth=dlq_depth,
            tasks_by_status=tasks_by_status,
            success_rate=success_rate,
            worker_heartbeat=worker_heartbeat,
        )
