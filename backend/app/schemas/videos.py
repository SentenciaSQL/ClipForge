"""Source video and metadata schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class VideoMetadataOut(BaseModel):
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    aspect_ratio: str | None = None
    bitrate: int | None = None
    file_size_bytes: int = 0
    format_name: str | None = None
    video_stream_count: int = 0
    audio_stream_count: int = 0
    raw: dict[str, Any] | None = None


class SourceVideoOut(ORMModel):
    id: str
    project_id: str
    original_filename: str
    stored_path: str
    file_size_bytes: int
    content_type: str | None
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    video_codec: str | None
    audio_codec: str | None
    aspect_ratio: str | None
    bitrate: int | None
    status: str
    created_at: datetime
    updated_at: datetime
    metadata: VideoMetadataOut | None = None


class VideoImportResponse(BaseModel):
    project: dict[str, Any]
    video: SourceVideoOut
    message: str = "Video imported successfully"


class AnalyzeRequest(BaseModel):
    """Phase 1 stub — full analysis arrives in later phases."""

    language: str | None = Field(default=None, description="ISO language code or null for auto")
    whisper_model: str | None = None
    clip_count: int = Field(default=5, ge=1, le=50)
    min_duration: int = Field(default=12, ge=12, le=30)
    max_duration: int = Field(default=30, ge=12, le=60)
    subtitle_preset: str = "hormozi"
    reframing_mode: str = "auto"
