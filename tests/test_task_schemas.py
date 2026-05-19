"""Unit tests for task Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.enums import TaskStatus
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead


def test_task_create_accepts_valid_payload() -> None:
    schema = TaskCreate(
        task_type="send_email",
        payload={"to": "a@b.com"},
        max_retries=5,
    )

    assert schema.task_type == "send_email"
    assert schema.payload == {"to": "a@b.com"}
    assert schema.max_retries == 5


def test_task_create_rejects_blank_task_type() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TaskCreate(task_type="   ")

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("task_type",) for error in errors)


def test_task_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(task_type="echo", unknown_field=True)  # type: ignore[call-arg]


def test_task_create_rejects_negative_max_retries() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(task_type="echo", max_retries=-1)


def test_task_create_rejects_non_string_payload_keys() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(task_type="echo", payload={1: "bad"})  # type: ignore[dict-item]


def test_task_read_from_orm_task() -> None:
    now = datetime.now(timezone.utc)
    orm_task = Task(
        id=uuid.uuid4(),
        task_type="slow_job",
        payload={"n": 1},
        status=TaskStatus.RUNNING,
        retry_count=1,
        max_retries=3,
        error_message=None,
        created_at=now,
        updated_at=now,
        started_at=now,
        completed_at=None,
    )

    read = TaskRead.from_orm_task(orm_task)

    assert read.id == orm_task.id
    assert read.task_type == "slow_job"
    assert read.status == TaskStatus.RUNNING
    assert read.retry_count == 1
    assert read.started_at == now
    assert read.completed_at is None


def test_task_read_serializes_to_json_compatible_dict() -> None:
    task_id = uuid.uuid4()
    now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    read = TaskRead(
        id=task_id,
        task_type="echo",
        payload=None,
        status=TaskStatus.COMPLETED,
        retry_count=0,
        max_retries=3,
        error_message=None,
        created_at=now,
        updated_at=now,
        started_at=now,
        completed_at=now,
    )

    data = read.model_dump(mode="json")

    assert data["id"] == str(task_id)
    assert data["status"] == "completed"
    assert data["completed_at"] is not None
