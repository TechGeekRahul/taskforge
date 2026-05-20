"""Authentication endpoint tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import API_V1


@pytest.mark.anyio
async def test_token_endpoint_returns_jwt() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"{API_V1}/auth/token",
            data={"username": "admin", "password": "admin"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 10


@pytest.mark.anyio
async def test_token_endpoint_rejects_bad_credentials() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"{API_V1}/auth/token",
            data={"username": "admin", "password": "wrong"},
        )

    assert response.status_code == 401
