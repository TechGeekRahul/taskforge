"""Process a single dequeued task message."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.enums import TaskStatus
from app.models.task import Task
from app.queue.dead_letter import DeadLetterMessage, DeadLetterReason
from app.queue.task_queue import TaskQueue, TaskQueueMessage
from app.worker.handlers import get_handler
from app.worker.retry_policy import compute_backoff_seconds

logger = logging.getLogger(__name__)


class TaskProcessor:
    """Loads a task from the database, runs its handler, and updates status."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._queue = TaskQueue.from_settings(redis, self._settings)

    async def process(self, message: TaskQueueMessage) -> None:
        task = await self._session.get(Task, message.task_id)
        if task is None:
            logger.warning("dequeued unknown task_id=%s", message.task_id)
            return

        if task.status in {TaskStatus.CANCELLED, TaskStatus.COMPLETED, TaskStatus.DEAD_LETTER}:
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
            await self._send_to_dead_letter(
                task,
                message,
                f"Unknown task_type: {message.task_type}",
                DeadLetterReason.UNKNOWN_TASK_TYPE,
            )
            return

        try:
            await handler(message.payload)
        except Exception as exc:  # noqa: BLE001 — persist failure for observability
            logger.exception("task_id=%s handler failed", task.id)
            await self._handle_handler_failure(task, message, str(exc))
            return

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        task.error_message = None
        await self._session.flush()
        logger.info("task_id=%s completed", task.id)

    async def _handle_handler_failure(
        self,
        task: Task,
        message: TaskQueueMessage,
        error: str,
    ) -> None:
        task.error_message = error[:2000]

        if task.retry_count >= task.max_retries:
            await self._send_to_dead_letter(
                task,
                message,
                error,
                DeadLetterReason.MAX_RETRIES_EXCEEDED,
            )
            return

        task.retry_count += 1
        delay = compute_backoff_seconds(
            task.retry_count,
            base_seconds=self._settings.retry_backoff_base_seconds,
            max_seconds=self._settings.retry_backoff_max_seconds,
        )
        task.status = TaskStatus.QUEUED
        task.started_at = None
        await self._session.flush()

        await self._queue.enqueue_delayed(message, delay_seconds=delay)
        logger.warning(
            "task_id=%s scheduled retry %s/%s in %.1fs",
            task.id,
            task.retry_count,
            task.max_retries,
            delay,
        )

    async def _send_to_dead_letter(
        self,
        task: Task,
        message: TaskQueueMessage,
        error: str,
        reason: str,
    ) -> None:
        """Mark task dead-lettered in Postgres and push a record to the Redis DLQ."""
        error_text = error[:2000]
        now = datetime.now(timezone.utc)

        removed = await self._queue.remove_pending_retries(task.id)
        if removed:
            logger.info(
                "removed %s pending retry entr%s for task_id=%s",
                removed,
                "y" if removed == 1 else "ies",
                task.id,
            )

        record = DeadLetterMessage(
            task_id=task.id,
            task_type=message.task_type,
            payload=message.payload,
            error_message=error_text,
            retry_count=task.retry_count,
            max_retries=task.max_retries,
            reason=reason,
            failed_at=now,
        )
        await self._queue.send_to_dlq(record)

        task.status = TaskStatus.DEAD_LETTER
        task.error_message = error_text
        task.completed_at = now
        await self._session.flush()
        logger.warning(
            "task_id=%s moved to dead-letter queue reason=%s",
            task.id,
            reason,
        )
