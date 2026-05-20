"""Tests for worker task processing."""

from __future__ import annotations

import uuid

import fakeredis.aioredis
import pytest
from sqlalchemy import select

from app.models.enums import TaskStatus
from app.models.task import Task
from app.queue.task_queue import TaskQueue, TaskQueueMessage
from app.schemas.task import TaskCreate
from app.services.task_service import TaskService
from app.worker.processor import TaskProcessor


@pytest.mark.anyio
async def test_processor_completes_echo_task(db_session) -> None:
    task = Task(
        task_type="echo",
        payload={"message": "hello"},
        status=TaskStatus.QUEUED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    processor = TaskProcessor(db_session)
    await processor.process(
        TaskQueueMessage(
            task_id=task.id,
            task_type="echo",
            payload={"message": "hello"},
        ),
    )
    await db_session.commit()

    result = await db_session.execute(select(Task).where(Task.id == task.id))
    stored = result.scalar_one()
    assert stored.status == TaskStatus.COMPLETED
    assert stored.started_at is not None
    assert stored.completed_at is not None
    assert stored.error_message is None


@pytest.mark.anyio
async def test_processor_marks_unknown_task_type_failed(db_session) -> None:
    task = Task(
        task_type="unknown_handler",
        status=TaskStatus.QUEUED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    processor = TaskProcessor(db_session)
    await processor.process(
        TaskQueueMessage(task_id=task.id, task_type="unknown_handler"),
    )
    await db_session.commit()

    result = await db_session.execute(select(Task).where(Task.id == task.id))
    stored = result.scalar_one()
    assert stored.status == TaskStatus.FAILED
    assert "Unknown task_type" in (stored.error_message or "")


@pytest.mark.anyio
async def test_end_to_end_submit_and_process(db_session) -> None:
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = TaskService(session=db_session, redis=fake_redis)
    task = await service.submit(TaskCreate(task_type="noop"))
    await db_session.commit()

    queue = TaskQueue.from_settings(fake_redis)
    message = await queue.dequeue(timeout=1)
    assert message is not None
    assert message.task_id == task.id

    processor = TaskProcessor(db_session)
    await processor.process(message)
    await db_session.commit()

    result = await db_session.execute(select(Task).where(Task.id == task.id))
    stored = result.scalar_one()
    assert stored.status == TaskStatus.COMPLETED

    await fake_redis.aclose()
