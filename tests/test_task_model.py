"""Integration tests for the Task ORM model."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task import Task


@pytest.mark.anyio
async def test_task_persists_with_defaults(db_session: AsyncSession) -> None:
    task = Task(task_type="echo", payload={"message": "hello"})
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    assert isinstance(task.id, uuid.UUID)
    assert task.status == TaskStatus.PENDING
    assert task.retry_count == 0
    assert task.max_retries == 3
    assert task.error_message is None
    assert task.started_at is None
    assert task.completed_at is None
    assert task.created_at is not None
    assert task.updated_at is not None


@pytest.mark.anyio
async def test_task_status_and_retry_fields_update(db_session: AsyncSession) -> None:
    task = Task(
        task_type="slow_job",
        status=TaskStatus.RUNNING,
        retry_count=2,
        max_retries=5,
        error_message="transient timeout",
    )
    db_session.add(task)
    await db_session.commit()

    result = await db_session.execute(select(Task).where(Task.id == task.id))
    loaded = result.scalar_one()

    assert loaded.status == TaskStatus.RUNNING
    assert loaded.retry_count == 2
    assert loaded.max_retries == 5
    assert loaded.error_message == "transient timeout"


@pytest.mark.anyio
async def test_task_status_enum_values() -> None:
    assert TaskStatus.DEAD_LETTER.value == "dead_letter"
    assert len(TaskStatus) == 7
