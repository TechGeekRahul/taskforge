"""API tests for task routes."""

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
from app.models.enums import TaskStatus
from app.queue.redis_client import close_redis, get_redis
from tests.conftest import API_V1


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
async def test_post_tasks_requires_auth(api_client: AsyncClient) -> None:
    response = await api_client.post(f"{API_V1}/tasks", json={"task_type": "noop"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_post_tasks_returns_201_and_enqueues(
    api_client: AsyncClient,
    fake_redis: Redis,
    auth_headers: dict[str, str],
) -> None:
    response = await api_client.post(
        f"{API_V1}/tasks",
        json={"task_type": "send_email", "payload": {"to": "a@b.com"}},
        headers=auth_headers,
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
async def test_get_task_returns_200(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await api_client.post(
        f"{API_V1}/tasks",
        json={"task_type": "noop"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    task_id = created.json()["id"]

    response = await api_client.get(f"{API_V1}/tasks/{task_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == task_id
    assert body["task_type"] == "noop"
    assert body["status"] == TaskStatus.QUEUED.value


@pytest.mark.anyio
async def test_get_task_returns_404_for_unknown_id(api_client: AsyncClient) -> None:
    response = await api_client.get(
        f"{API_V1}/tasks/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )

    assert response.status_code == 404
    assert response.json().get("detail") == "Task not found"


@pytest.mark.anyio
async def test_get_task_returns_422_for_invalid_uuid(api_client: AsyncClient) -> None:
    response = await api_client.get(f"{API_V1}/tasks/not-a-uuid")

    assert response.status_code == 422


@pytest.mark.anyio
async def test_delete_task_cancels_queued_task(
    api_client: AsyncClient,
    fake_redis: Redis,
    auth_headers: dict[str, str],
) -> None:
    created = await api_client.post(
        f"{API_V1}/tasks",
        json={"task_type": "noop"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    task_id = created.json()["id"]

    queue_key = get_settings().task_queue_key
    assert len(await fake_redis.lrange(queue_key, 0, -1)) == 1

    response = await api_client.delete(f"{API_V1}/tasks/{task_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == TaskStatus.CANCELLED.value
    assert body["completed_at"] is not None
    assert await fake_redis.llen(queue_key) == 0


@pytest.mark.anyio
async def test_delete_task_returns_409_when_already_cancelled(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await api_client.post(
        f"{API_V1}/tasks",
        json={"task_type": "noop"},
        headers=auth_headers,
    )
    task_id = created.json()["id"]
    await api_client.delete(f"{API_V1}/tasks/{task_id}")

    again = await api_client.delete(f"{API_V1}/tasks/{task_id}")
    assert again.status_code == 409


@pytest.mark.anyio
async def test_delete_task_returns_404(api_client: AsyncClient) -> None:
    response = await api_client.delete(
        f"{API_V1}/tasks/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_post_tasks_validates_body(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await api_client.post(
        f"{API_V1}/tasks",
        json={"task_type": ""},
        headers=auth_headers,
    )

    assert response.status_code == 422
