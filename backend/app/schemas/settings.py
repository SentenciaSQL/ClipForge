"""Application settings schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AppSettingsOut(BaseModel):
    ollama_url: str
    ollama_model: str
    whisper_model: str
    whisper_device: str
    prefer_gpu: bool
    max_concurrent_jobs: int
    use_nvenc: str
    ffmpeg_path: str | None
    ffprobe_path: str | None
    workspace_path: str
    output_width: int
    output_height: int
    output_fps: int
    crf: int
    clip_min_seconds: int
    clip_max_seconds: int
    hardware: dict[str, Any]


class AppSettingsUpdate(BaseModel):
    ollama_url: str | None = None
    ollama_model: str | None = None
    whisper_model: str | None = None
    whisper_device: Literal["auto", "cuda", "cpu"] | None = None
    prefer_gpu: bool | None = None
    max_concurrent_jobs: int | None = Field(default=None, ge=1, le=4)
    use_nvenc: Literal["auto", "true", "false"] | None = None
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    workspace_path: str | None = None
    output_width: int | None = None
    output_height: int | None = None
    output_fps: int | None = None
    crf: int | None = Field(default=None, ge=12, le=28)
    clip_min_seconds: int | None = Field(default=None, ge=12, le=30)
    clip_max_seconds: int | None = Field(default=None, ge=12, le=60)


class HealthOut(BaseModel):
    status: str
    version: str
    hardware: dict[str, Any]
