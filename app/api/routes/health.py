"""Health check routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis_dep, get_session_dep
from app.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health")
async def health(
    session: AsyncSession = Depends(get_session_dep),
    redis: Redis = Depends(get_redis_dep),
) -> JSONResponse:
    report = await HealthService(session, redis).check()
    code = status.HTTP_200_OK if report.status == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=report.to_dict(), status_code=code)
