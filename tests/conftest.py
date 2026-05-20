"""Shared pytest fixtures for database-backed tests."""

from __future__ import annotations

import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("AUTH_USERNAME", "admin")
os.environ.setdefault("AUTH_PASSWORD", "admin")

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import dispose_engine

get_settings.cache_clear()
from app.models import task  # noqa: F401 — register ORM models

API_V1 = "/api/v1"


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = create_access_token("test-client", get_settings())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://taskforge:taskforge@localhost:5432/taskforge",
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine(database_url: str) -> AsyncGenerator[AsyncEngine, None]:
    """Session-scoped engine; skips tests when PostgreSQL is unreachable."""
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except (OSError, Exception) as exc:  # noqa: BLE001 — connection errors vary by driver
        await engine.dispose()
        pytest.skip(f"PostgreSQL not available: {exc}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    await dispose_engine()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped session rolled back after each test."""
    factory = async_sessionmaker_for_engine(db_engine)
    async with factory() as session:
        yield session
        await session.rollback()


def async_sessionmaker_for_engine(engine: AsyncEngine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
