"""Highlight and clip response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class HighlightOut(ORMModel):
    id: str
    video_id: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    transcript: str | None
    hook: str | None
    category: str | None
    description: str | None
    score: float
    score_breakdown: dict[str, Any] | None = None
    reason: str | None
    selected: bool
    rank: int | None
    created_at: datetime


class ClipOut(ORMModel):
    id: str
    project_id: str
    video_id: str
    highlight_id: str | None
    title: str | None
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    score: float
    category: str | None
    hook: str | None
    transcript: str | None
    reframing_mode: str
    status: str
    output_path: str | None
    created_at: datetime
    updated_at: datetime


class HighlightsRequest(BaseModel):
    clip_count: int = Field(default=5, ge=1, le=50)
    min_duration: int = Field(default=12, ge=12, le=30)
    max_duration: int = Field(default=30, ge=12, le=60)
    ollama_model: str | None = None
    subtitle_preset: str = "hormozi"
