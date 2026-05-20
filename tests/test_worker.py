"""Tests for worker task processing."""

from __future__ import annotations

import fakeredis.aioredis
import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.models.enums import TaskStatus
from app.models.task import Task
from app.queue.task_queue import TaskQueue, TaskQueueMessage
from app.schemas.task import TaskCreate
from app.services.task_service import TaskService
from app.worker.processor import TaskProcessor


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        retry_backoff_base_seconds=0.0,
        retry_backoff_max_seconds=300.0,
        task_queue_key="test:queue",
        task_retry_queue_key="test:retry",
    )


@pytest.fixture
async def fake_redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.mark.anyio
async def test_processor_completes_echo_task(db_session, fake_redis, test_settings) -> None:
    task = Task(
        task_type="echo",
        payload={"message": "hello"},
        status=TaskStatus.QUEUED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    processor = TaskProcessor(db_session, redis=fake_redis, settings=test_settings)
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
async def test_processor_marks_unknown_task_type_failed(
    db_session,
    fake_redis,
    test_settings,
) -> None:
    task = Task(
        task_type="unknown_handler",
        status=TaskStatus.QUEUED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    processor = TaskProcessor(db_session, redis=fake_redis, settings=test_settings)
    await processor.process(
        TaskQueueMessage(task_id=task.id, task_type="unknown_handler"),
    )
    await db_session.commit()

    result = await db_session.execute(select(Task).where(Task.id == task.id))
    stored = result.scalar_one()
    assert stored.status == TaskStatus.FAILED
    assert stored.retry_count == 0
    assert "Unknown task_type" in (stored.error_message or "")


@pytest.mark.anyio
async def test_processor_schedules_retry_on_handler_failure(
    db_session,
    fake_redis,
    test_settings,
) -> None:
    task = Task(
        task_type="always_fail",
        status=TaskStatus.QUEUED,
        max_retries=3,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    message = TaskQueueMessage(task_id=task.id, task_type="always_fail")
    processor = TaskProcessor(db_session, redis=fake_redis, settings=test_settings)
    await processor.process(message)
    await db_session.commit()

    result = await db_session.execute(select(Task).where(Task.id == task.id))
    stored = result.scalar_one()
    assert stored.status == TaskStatus.QUEUED
    assert stored.retry_count == 1
    assert "simulated handler failure" in (stored.error_message or "")

    queue = TaskQueue(
        redis=fake_redis,
        queue_key=test_settings.task_queue_key,
        retry_queue_key=test_settings.task_retry_queue_key,
    )
    assert await queue.retry_depth() == 1

    released = await queue.release_due_retries()
    assert released == 1
    assert await queue.depth() == 1


@pytest.mark.anyio
async def test_processor_permanent_failure_when_retries_exhausted(
    db_session,
    fake_redis,
    test_settings,
) -> None:
    task = Task(
        task_type="always_fail",
        status=TaskStatus.QUEUED,
        retry_count=3,
        max_retries=3,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    processor = TaskProcessor(db_session, redis=fake_redis, settings=test_settings)
    await processor.process(
        TaskQueueMessage(task_id=task.id, task_type="always_fail"),
    )
    await db_session.commit()

    result = await db_session.execute(select(Task).where(Task.id == task.id))
    stored = result.scalar_one()
    assert stored.status == TaskStatus.FAILED
    assert stored.retry_count == 3

    queue = TaskQueue(
        redis=fake_redis,
        queue_key=test_settings.task_queue_key,
        retry_queue_key=test_settings.task_retry_queue_key,
    )
    assert await queue.retry_depth() == 0


@pytest.mark.anyio
async def test_end_to_end_submit_and_process(db_session, fake_redis, test_settings) -> None:
    service = TaskService(session=db_session, redis=fake_redis)
    task = await service.submit(TaskCreate(task_type="noop"))
    await db_session.commit()

    queue = TaskQueue(
        redis=fake_redis,
        queue_key=test_settings.task_queue_key,
        retry_queue_key=test_settings.task_retry_queue_key,
    )
    message = await queue.dequeue(timeout=1)
    assert message is not None
    assert message.task_id == task.id

    processor = TaskProcessor(db_session, redis=fake_redis, settings=test_settings)
    await processor.process(message)
    await db_session.commit()

    result = await db_session.execute(select(Task).where(Task.id == task.id))
    stored = result.scalar_one()
    assert stored.status == TaskStatus.COMPLETED
