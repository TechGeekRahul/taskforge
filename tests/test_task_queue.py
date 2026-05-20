"""Unit tests for Redis task queue."""

from __future__ import annotations

import uuid

import fakeredis.aioredis
import pytest

from app.queue.task_queue import TaskQueue, TaskQueueMessage


@pytest.mark.anyio
async def test_enqueue_and_dequeue_fifo() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    queue = TaskQueue(redis=redis, queue_key="test:queue")

    first = TaskQueueMessage(
        task_id=uuid.uuid4(),
        task_type="noop",
        payload=None,
    )
    second = TaskQueueMessage(
        task_id=uuid.uuid4(),
        task_type="echo",
        payload={"message": "b"},
    )

    await queue.enqueue(first)
    await queue.enqueue(second)

    assert await queue.depth() == 2

    dequeued_first = await queue.dequeue(timeout=1)
    dequeued_second = await queue.dequeue(timeout=1)

    assert dequeued_first is not None
    assert dequeued_second is not None
    assert dequeued_first.task_id == first.task_id
    assert dequeued_second.task_id == second.task_id
    assert await queue.depth() == 0

    await redis.aclose()
