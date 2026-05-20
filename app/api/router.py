"""Aggregate API routers."""

from fastapi import APIRouter

from app.api.routes import auth, tasks

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth.router)
v1_router.include_router(tasks.router)
