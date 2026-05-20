"""API tests for POST /tasks."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import get_settings
from app.db.session import dispose_engine, get_session
from app.main import app
from app.queue.redis_client import close_redis, get_redis
from app.models.enums import TaskStatus


@pytest_asyncio.fixture
async def fake_redis() -> AsyncGenerator[Redis, None]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def api_client(
    db_engine: AsyncEngine,
    fake_redis: Redis,
) -> AsyncGenerator[AsyncClient, None]:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_redis() -> AsyncGenerator[Redis, None]:
        yield fake_redis

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
    await close_redis()
    await dispose_engine()


@pytest.mark.anyio
async def test_post_tasks_returns_201_and_enqueues(api_client: AsyncClient, fake_redis: Redis) -> None:
    response = await api_client.post(
        "/tasks",
        json={"task_type": "send_email", "payload": {"to": "a@b.com"}},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["task_type"] == "send_email"
    assert body["status"] == TaskStatus.QUEUED.value
    assert body["retry_count"] == 0
    assert "id" in body
    assert "created_at" in body

    queue_key = get_settings().task_queue_key
    messages = await fake_redis.lrange(queue_key, 0, -1)
    assert len(messages) == 1
    queued = json.loads(messages[0])
    assert queued["task_id"] == body["id"]


@pytest.mark.anyio
async def test_post_tasks_validates_body(api_client: AsyncClient) -> None:
    response = await api_client.post("/tasks", json={"task_type": ""})

    assert response.status_code == 422
