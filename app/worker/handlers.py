"""Registered task handlers invoked by the worker."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

TaskHandler = Callable[[dict[str, Any] | None], Awaitable[None]]

_REGISTRY: dict[str, TaskHandler] = {}


def register(task_type: str) -> Callable[[TaskHandler], TaskHandler]:
    """Decorator that registers an async handler for a task_type."""

    def decorator(func: TaskHandler) -> TaskHandler:
        _REGISTRY[task_type] = func
        return func

    return decorator


def get_handler(task_type: str) -> TaskHandler | None:
    return _REGISTRY.get(task_type)


def registered_task_types() -> frozenset[str]:
    return frozenset(_REGISTRY)


@register("noop")
async def noop_handler(_payload: dict[str, Any] | None) -> None:
    """No-op handler for plumbing and integration tests."""


@register("echo")
async def echo_handler(payload: dict[str, Any] | None) -> None:
    """Validate echo payload; workers log completion via DB status updates."""
    if payload is None or "message" not in payload:
        raise ValueError("echo task requires payload.message")
