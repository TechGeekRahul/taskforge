"""Dependency health checks for /health."""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    status: str
    detail: str | None = None


@dataclass(frozen=True)
class HealthReport:
    status: str
    components: list[ComponentHealth]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "components": [
                {"name": c.name, "status": c.status, "detail": c.detail}
                for c in self.components
            ],
        }


class HealthService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings or get_settings()

    async def check(self) -> HealthReport:
        components: list[ComponentHealth] = []

        components.append(await self._check_postgres())
        components.append(await self._check_redis())
        components.append(await self._check_worker())

        overall = (
            "healthy"
            if all(c.status == "up" for c in components)
            else "degraded"
        )
        return HealthReport(status=overall, components=components)

    async def _check_postgres(self) -> ComponentHealth:
        try:
            await self._session.execute(text("SELECT 1"))
            return ComponentHealth(name="postgres", status="up")
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth(
                name="postgres",
                status="down",
                detail=str(exc),
            )

    async def _check_redis(self) -> ComponentHealth:
        try:
            pong = await self._redis.ping()
            if pong:
                return ComponentHealth(name="redis", status="up")
            return ComponentHealth(name="redis", status="down", detail="no pong")
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth(name="redis", status="down", detail=str(exc))

    async def _check_worker(self) -> ComponentHealth:
        try:
            heartbeat = await self._redis.get(self._settings.worker_heartbeat_key)
            if heartbeat:
                return ComponentHealth(name="worker", status="up", detail=heartbeat)
            return ComponentHealth(
                name="worker",
                status="down",
                detail="no recent heartbeat",
            )
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth(name="worker", status="down", detail=str(exc))
