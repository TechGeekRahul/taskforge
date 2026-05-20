"""Task submission orchestration (database + queue)."""

from __future__ import annotations

import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task import Task
from app.queue.task_queue import TaskQueue, TaskQueueMessage
from app.schemas.task import TaskCreate


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
        return task

    async def get_by_id(self, task_id: uuid.UUID) -> Task | None:
        """Load a task by primary key for status and detail responses."""
        return await self._session.get(Task, task_id)
