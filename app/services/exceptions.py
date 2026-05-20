"""Domain exceptions raised by application services."""


class TaskNotFoundError(Exception):
    """No task exists for the given id."""


class TaskNotCancellableError(Exception):
    """Task is in a terminal or non-cancellable state."""
