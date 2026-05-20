"""Dead-letter queue message schema."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeadLetterReason:
    """Known reasons a task was moved to the dead-letter queue."""

    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    UNKNOWN_TASK_TYPE = "unknown_task_type"
    HANDLER_FAILURE = "handler_failure"


class DeadLetterMessage(BaseModel):
    """Snapshot of a permanently failed task stored in the DLQ for inspection."""

    model_config = ConfigDict(extra="forbid")

    task_id: uuid.UUID
    task_type: str
    payload: dict[str, Any] | None = None
    error_message: str
    retry_count: int
    max_retries: int
    reason: str
    failed_at: datetime = Field(description="UTC timestamp when the task was dead-lettered")
