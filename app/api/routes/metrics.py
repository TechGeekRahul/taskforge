"""Metrics routes (JSON summary and Prometheus scrape)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis_dep, get_session_dep
from app.observability.prometheus import prometheus_content
from app.services.metrics_service import MetricsService

router = APIRouter(tags=["metrics"])


@router.get("/metrics", summary="Operational metrics (JSON)")
async def metrics_json(
    session: AsyncSession = Depends(get_session_dep),
    redis: Redis = Depends(get_redis_dep),
) -> dict:
    """Queue depths, task counts by status, and success rate."""
    snapshot = await MetricsService(session, redis).snapshot()
    return snapshot.to_dict()


@router.get(
    "/metrics/prometheus",
    summary="Prometheus metrics",
    response_class=PlainTextResponse,
)
async def metrics_prometheus() -> Response:
    """Prometheus text exposition format."""
    return Response(
        content=prometheus_content(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
