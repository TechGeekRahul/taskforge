"""Request and task context propagated through logs."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
task_id_var: ContextVar[str | None] = ContextVar("task_id", default=None)


def get_correlation_id() -> str | None:
    return correlation_id_var.get()


def set_correlation_id(value: str | None) -> None:
    correlation_id_var.set(value)


def get_task_id() -> str | None:
    return task_id_var.get()


def set_task_id(value: str | uuid.UUID | None) -> None:
    if value is None:
        task_id_var.set(None)
    else:
        task_id_var.set(str(value))


def bind_task_context(task_id: str | uuid.UUID | None) -> None:
    set_task_id(task_id)
