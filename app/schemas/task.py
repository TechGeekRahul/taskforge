"""Pydantic schemas for task submission and status responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TaskStatus
from app.models.task import Task

TASK_TYPE_MAX_LENGTH = 128
MAX_RETRIES_UPPER_BOUND = 10


class TaskCreate(BaseModel):
    """Request body for submitting a new background task."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "task_type": "send_email",
                "payload": {"to": "user@example.com", "subject": "Hello"},
                "max_retries": 3,
            }
        },
    )

    task_type: str = Field(
        ...,
        min_length=1,
        max_length=TASK_TYPE_MAX_LENGTH,
        description="Handler identifier registered by workers.",
    )
    payload: dict[str, Any] | None = Field(
        default=None,
        description="JSON-serializable arguments passed to the task handler.",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=MAX_RETRIES_UPPER_BOUND,
        description="Maximum retry attempts after transient failures.",
    )

    @field_validator("task_type")
    @classmethod
    def task_type_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("task_type must not be empty or whitespace only")
        return value


class TaskRead(BaseModel):
    """Full task representation returned by status and detail endpoints."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "task_type": "send_email",
                "payload": {"to": "user@example.com"},
                "status": "pending",
                "retry_count": 0,
                "max_retries": 3,
                "error_message": None,
                "created_at": "2026-05-19T12:00:00+00:00",
                "updated_at": "2026-05-19T12:00:00+00:00",
                "started_at": None,
                "completed_at": None,
            }
        },
    )

    id: uuid.UUID
    task_type: str
    payload: dict[str, Any] | None
    status: TaskStatus
    retry_count: int
    max_retries: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_orm_task(cls, task: Task) -> TaskRead:
        """Build a response model from a SQLAlchemy Task instance."""
        return cls.model_validate(task)
