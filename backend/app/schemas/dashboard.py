"""Dashboard aggregate schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.schemas.jobs import ProcessingJobOut
from app.schemas.projects import ProjectOut


class DashboardStats(BaseModel):
    total_projects: int
    imported_videos: int
    generated_clips: int
    active_jobs: int
    recent_projects: list[ProjectOut]
    recent_jobs: list[ProcessingJobOut]
    hardware: dict[str, Any]
