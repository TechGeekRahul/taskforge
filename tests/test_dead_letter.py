"""Unit tests for dead-letter queue operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import fakeredis.aioredis
import pytest

from app.queue.dead_letter import DeadLetterMessage, DeadLetterReason
from app.queue.task_queue import TaskQueue, TaskQueueMessage


@pytest.mark.anyio
async def test_send_to_dlq_and_remove_pending_retries() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    queue = TaskQueue(
        redis=redis,
        queue_key="test:queue",
        retry_queue_key="test:retry",
        dlq_key="test:dlq",
    )
    task_id = uuid.uuid4()
    message = TaskQueueMessage(task_id=task_id, task_type="always_fail")
    await queue.enqueue_delayed(message, delay_seconds=60)
    assert await queue.retry_depth() == 1

    removed = await queue.remove_pending_retries(task_id)
    assert removed == 1
    assert await queue.retry_depth() == 0

    record = DeadLetterMessage(
        task_id=task_id,
        task_type="always_fail",
        error_message="boom",
        retry_count=3,
        max_retries=3,
        reason=DeadLetterReason.MAX_RETRIES_EXCEEDED,
        failed_at=datetime.now(timezone.utc),
    )
    await queue.send_to_dlq(record)
    assert await queue.dlq_depth() == 1

    raw = await redis.lindex("test:dlq", 0)
    parsed = DeadLetterMessage.model_validate_json(raw)
    assert parsed.task_id == task_id
    assert parsed.reason == DeadLetterReason.MAX_RETRIES_EXCEEDED

    await redis.aclose()
