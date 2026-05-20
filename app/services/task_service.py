"""Task submission orchestration (database + queue)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task import Task
from app.queue.task_queue import TaskQueue, TaskQueueMessage
from app.schemas.task import TaskCreate
from app.core.context import bind_task_context
from app.observability import prometheus as prom
from app.services.exceptions import TaskNotCancellableError, TaskNotFoundError

logger = logging.getLogger(__name__)

CANCELLABLE_STATUSES = frozenset({
    TaskStatus.PENDING,
    TaskStatus.QUEUED,
    TaskStatus.RUNNING,
})


class TaskEnqueueError(Exception):
    """Raised when a persisted task cannot be enqueued to Redis."""


class TaskService:
    """Coordinates task persistence and Redis enqueue."""

    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._queue = TaskQueue.from_settings(redis)

    async def submit(self, body: TaskCreate) -> Task:
        """
        Create a task record and enqueue it for workers.

        On Redis failure the database transaction is rolled back by the session
        dependency; no orphaned PENDING rows are left without a queue message.
        """
        task = Task(
            task_type=body.task_type,
            payload=body.payload,
            max_retries=body.max_retries,
            status=TaskStatus.PENDING,
        )
        self._session.add(task)
        await self._session.flush()
        bind_task_context(task.id)

        message = TaskQueueMessage(
            task_id=task.id,
            task_type=task.task_type,
            payload=task.payload,
        )

        try:
            await self._queue.enqueue(message)
        except Exception as exc:  # noqa: BLE001 — re-raised as domain error
            raise TaskEnqueueError("Failed to enqueue task") from exc

        task.status = TaskStatus.QUEUED
        await self._session.flush()
        await self._session.refresh(task)
        prom.record_submitted(task.task_type)
        logger.info("task submitted task_type=%s", task.task_type)
        return task

    async def get_by_id(self, task_id: uuid.UUID) -> Task | None:
        """Load a task by primary key for status and detail responses."""
        return await self._session.get(Task, task_id)

    async def cancel(self, task_id: uuid.UUID) -> Task:
        """
        Cancel a task that has not finished processing.

        Removes pending queue and retry entries so workers will not pick it up.
        """
        task = await self.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError()

        if task.status not in CANCELLABLE_STATUSES:
            raise TaskNotCancellableError(
                f"Task in status '{task.status.value}' cannot be cancelled",
            )

        await self._queue.remove_from_main_queue(task.id)
        await self._queue.remove_pending_retries(task.id)

        now = datetime.now(timezone.utc)
        task.status = TaskStatus.CANCELLED
        task.completed_at = now
        await self._session.flush()
        await self._session.refresh(task)
        return task
