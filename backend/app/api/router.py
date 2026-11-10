"""Aggregate API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import dashboard, health, highlights, jobs, projects, settings, transcriptions, videos

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(videos.router, tags=["videos"])
api_router.include_router(transcriptions.router, tags=["transcriptions"])
api_router.include_router(highlights.router, tags=["highlights"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(settings.router, tags=["settings"])
