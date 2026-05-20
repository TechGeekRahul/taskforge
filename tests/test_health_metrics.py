"""Health and metrics endpoint tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.main import app
from tests.conftest import API_V1
from tests.test_api_tasks import api_client, fake_redis  # noqa: F401 — reuse fixtures


@pytest.mark.anyio
async def test_health_returns_components(api_client: AsyncClient) -> None:
    response = await api_client.get("/health")
    assert response.status_code in {200, 503}
    body = response.json()
    assert "status" in body
    assert "components" in body
    names = {c["name"] for c in body["components"]}
    assert "postgres" in names
    assert "redis" in names
    assert "worker" in names


@pytest.mark.anyio
async def test_metrics_json(api_client: AsyncClient, auth_headers: dict) -> None:
    await api_client.post(
        f"{API_V1}/tasks",
        json={"task_type": "noop"},
        headers=auth_headers,
    )
    response = await api_client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert "queue_depth" in body
    assert "tasks_by_status" in body
    assert "success_rate" in body


@pytest.mark.anyio
async def test_metrics_prometheus_exposition() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/metrics/prometheus")

    assert response.status_code == 200
    assert "taskforge_tasks_submitted_total" in response.text


@pytest.mark.anyio
async def test_correlation_id_header() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/", headers={"X-Correlation-ID": "test-corr-123"})

    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == "test-corr-123"
