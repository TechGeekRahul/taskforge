"""Unit tests for task submission service."""

from __future__ import annotations

import json
import uuid

import fakeredis.aioredis
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.enums import TaskStatus
from app.models.task import Task
from app.schemas.task import TaskCreate
from app.services.task_service import TaskEnqueueError, TaskService


@pytest.mark.anyio
async def test_submit_persists_and_enqueues(db_session) -> None:
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = TaskService(session=db_session, redis=fake_redis)
    body = TaskCreate(task_type="echo", payload={"message": "hi"})

    task = await service.submit(body)
    await db_session.commit()

    queue_key = get_settings().task_queue_key
    raw_messages = await fake_redis.lrange(queue_key, 0, -1)
    assert len(raw_messages) == 1

    message = json.loads(raw_messages[0])
    assert message["task_id"] == str(task.id)
    assert message["task_type"] == "echo"
    assert message["payload"] == {"message": "hi"}

    result = await db_session.execute(select(Task).where(Task.id == task.id))
    stored = result.scalar_one()
    assert stored.status == TaskStatus.QUEUED
    assert stored.retry_count == 0


@pytest.mark.anyio
async def test_submit_leaves_no_row_when_enqueue_fails(db_session, monkeypatch) -> None:
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = TaskService(session=db_session, redis=fake_redis)

    async def fail_enqueue(_self, _message):  # noqa: ANN001
        raise ConnectionError("redis down")

    monkeypatch.setattr(service._queue, "enqueue", fail_enqueue)  # noqa: SLF001

    with pytest.raises(TaskEnqueueError):
        await service.submit(TaskCreate(task_type="echo"))

    await db_session.rollback()

    result = await db_session.execute(select(Task))
    assert result.scalars().all() == []


@pytest.mark.anyio
async def test_get_by_id_returns_task(db_session) -> None:
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = TaskService(session=db_session, redis=fake_redis)
    task = await service.submit(TaskCreate(task_type="noop"))
    await db_session.commit()

    loaded = await service.get_by_id(task.id)
    assert loaded is not None
    assert loaded.id == task.id


@pytest.mark.anyio
async def test_get_by_id_returns_none(db_session) -> None:
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = TaskService(session=db_session, redis=fake_redis)

    loaded = await service.get_by_id(uuid.uuid4())
    assert loaded is None
