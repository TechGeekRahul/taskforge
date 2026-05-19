"""Domain enumerations persisted on task records."""

from enum import StrEnum


class TaskStatus(StrEnum):
    """Lifecycle states for a background task."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"
