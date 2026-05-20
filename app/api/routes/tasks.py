"""Task submission and status routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_task_service
from app.core.config import get_settings
from app.core.security import get_current_user
from app.schemas.task import TaskCreate, TaskRead
from app.services.exceptions import TaskNotCancellableError, TaskNotFoundError
from app.services.task_service import TaskEnqueueError, TaskService

limiter = Limiter(key_func=get_remote_address)


def _rate_limit() -> str:
    return get_settings().rate_limit


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a background task",
)
@limiter.limit(_rate_limit)
async def create_task(
    request: Request,
    body: TaskCreate,
    task_service: TaskService = Depends(get_task_service),
    _user: str = Depends(get_current_user),
) -> TaskRead:
    """Persist a task and enqueue it on Redis for worker processing."""
    try:
        task = await task_service.submit(body)
    except TaskEnqueueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue is unavailable",
        ) from exc

    return TaskRead.from_orm_task(task)


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    summary="Get task status",
)
async def get_task(
    task_id: uuid.UUID,
    task_service: TaskService = Depends(get_task_service),
) -> TaskRead:
    """Return the current persisted state of a task."""
    task = await task_service.get_by_id(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return TaskRead.from_orm_task(task)


@router.delete(
    "/{task_id}",
    response_model=TaskRead,
    summary="Cancel a task",
)
async def cancel_task(
    task_id: uuid.UUID,
    task_service: TaskService = Depends(get_task_service),
) -> TaskRead:
    """Cancel a pending, queued, or running task."""
    try:
        task = await task_service.cancel(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from exc
    except TaskNotCancellableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return TaskRead.from_orm_task(task)
