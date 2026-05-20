"""Exponential backoff calculations for task retries."""


def compute_backoff_seconds(
    retry_count: int,
    *,
    base_seconds: float,
    max_seconds: float,
) -> float:
    """
    Delay before the next attempt after a failure.

    ``retry_count`` is the value *after* incrementing on failure (1 = first retry).
    Uses ``min(base * 2^(retry_count - 1), max)``.
    """
    if retry_count < 1:
        raise ValueError("retry_count must be >= 1")
    if base_seconds <= 0:
        return 0.0
    delay = base_seconds * (2 ** (retry_count - 1))
    return min(delay, max_seconds)
