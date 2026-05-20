"""Unit tests for exponential backoff policy."""

from __future__ import annotations

import pytest

from app.worker.retry_policy import compute_backoff_seconds


def test_backoff_exponential_growth() -> None:
    assert compute_backoff_seconds(1, base_seconds=2.0, max_seconds=100.0) == 2.0
    assert compute_backoff_seconds(2, base_seconds=2.0, max_seconds=100.0) == 4.0
    assert compute_backoff_seconds(3, base_seconds=2.0, max_seconds=100.0) == 8.0


def test_backoff_capped_at_max() -> None:
    assert compute_backoff_seconds(10, base_seconds=1.0, max_seconds=30.0) == 30.0


def test_backoff_zero_base_is_immediate() -> None:
    assert compute_backoff_seconds(5, base_seconds=0.0, max_seconds=300.0) == 0.0


def test_backoff_requires_positive_retry_count() -> None:
    with pytest.raises(ValueError):
        compute_backoff_seconds(0, base_seconds=1.0, max_seconds=10.0)
