"""Process a single dequeued task message."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task import Task
from app.queue.task_queue import TaskQueueMessage
from app.worker.handlers import get_handler

logger = logging.getLogger(__name__)


class UnknownTaskTypeError(Exception):
    """Raised when no handler is registered for the task_type."""


class TaskProcessor:
    """Loads a task from the database, runs its handler, and updates status."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def process(self, message: TaskQueueMessage) -> None:
        task = await self._session.get(Task, message.task_id)
        if task is None:
            logger.warning("dequeued unknown task_id=%s", message.task_id)
            return

        if task.status in {TaskStatus.CANCELLED, TaskStatus.COMPLETED}:
            logger.info(
                "skipping task_id=%s status=%s",
                task.id,
                task.status,
            )
            return

        now = datetime.now(timezone.utc)
        task.status = TaskStatus.RUNNING
        task.started_at = now
        task.error_message = None
        await self._session.flush()

        handler = get_handler(message.task_type)
        if handler is None:
            await self._mark_failed(task, f"Unknown task_type: {message.task_type}")
            return

        try:
            await handler(message.payload)
        except Exception as exc:  # noqa: BLE001 — persist failure for observability
            logger.exception("task_id=%s handler failed", task.id)
            await self._mark_failed(task, str(exc))
            return

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        task.error_message = None
        await self._session.flush()
        logger.info("task_id=%s completed", task.id)

    async def _mark_failed(self, task: Task, error: str) -> None:
        task.status = TaskStatus.FAILED
        task.error_message = error[:2000]
        await self._session.flush()
        logger.warning("task_id=%s failed: %s", task.id, error)
