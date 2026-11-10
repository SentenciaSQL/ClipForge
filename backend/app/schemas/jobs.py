"""Processing job schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas.common import ORMModel


class ProcessingJobOut(ORMModel):
    id: str
    project_id: str | None
    video_id: str | None
    clip_id: str | None
    job_type: str
    status: str
    current_stage: str | None
    progress: float
    message: str | None
    error: str | None
    stages_json: list[dict[str, Any]] | None = None
    result_json: dict[str, Any] | None = None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
