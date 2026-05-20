"""Prometheus metric definitions and helpers."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest

TASKS_SUBMITTED = Counter(
    "taskforge_tasks_submitted_total",
    "Tasks submitted via the API",
    ["task_type"],
)
TASKS_COMPLETED = Counter(
    "taskforge_tasks_completed_total",
    "Tasks completed successfully",
    ["task_type"],
)
TASKS_FAILED = Counter(
    "taskforge_tasks_failed_total",
    "Tasks that entered a terminal failure state",
    ["task_type", "reason"],
)
QUEUE_DEPTH = Gauge("taskforge_queue_depth", "Main task queue depth")
RETRY_QUEUE_DEPTH = Gauge("taskforge_retry_queue_depth", "Delayed retry queue size")
DLQ_DEPTH = Gauge("taskforge_dlq_depth", "Dead-letter queue depth")
TASK_PROCESSING_SECONDS = Histogram(
    "taskforge_task_processing_seconds",
    "Task handler execution time",
    ["task_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)


def prometheus_content() -> bytes:
    return generate_latest()


def record_submitted(task_type: str) -> None:
    TASKS_SUBMITTED.labels(task_type=task_type).inc()


def record_completed(task_type: str) -> None:
    TASKS_COMPLETED.labels(task_type=task_type).inc()


def record_failed(task_type: str, reason: str) -> None:
    TASKS_FAILED.labels(task_type=task_type, reason=reason).inc()


def set_queue_depths(main: int, retry: int, dlq: int) -> None:
    QUEUE_DEPTH.set(main)
    RETRY_QUEUE_DEPTH.set(retry)
    DLQ_DEPTH.set(dlq)
