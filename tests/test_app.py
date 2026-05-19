"""Smoke tests for the API shell (Step 1)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_root_returns_service_metadata() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "taskforge"
    assert body["status"] == "ok"
    assert "version" in body
