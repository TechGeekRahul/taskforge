"""Structured logging tests."""

from __future__ import annotations

import json
import logging

from app.core.context import bind_task_context, set_correlation_id
from app.core.logging import JsonFormatter


def test_json_formatter_includes_context() -> None:
    set_correlation_id("corr-abc")
    bind_task_context("task-uuid-123")

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    line = JsonFormatter().format(record)
    payload = json.loads(line)

    assert payload["message"] == "hello"
    assert payload["correlation_id"] == "corr-abc"
    assert payload["task_id"] == "task-uuid-123"
