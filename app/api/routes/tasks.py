"""Task submission and status routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_task_service
from app.schemas.task import TaskCreate, TaskRead
from app.services.task_service import TaskEnqueueError, TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a background task",
)
async def create_task(
    body: TaskCreate,
    task_service: TaskService = Depends(get_task_service),
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
