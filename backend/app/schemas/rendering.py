"""Render / export request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RenderClipRequest(BaseModel):
    reframing_mode: str | None = None
    subtitle_preset: str | None = None
    burn_subtitles: bool | None = None
    preview: bool = False
    configuration: dict | None = None


class ExportClipsRequest(BaseModel):
    clip_ids: list[str] = Field(min_length=1)
    render_if_needed: bool = True


class PatchClipRequest(BaseModel):
    title: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    reframing_mode: str | None = None
    subtitle_preset_id: str | None = None
    status: str | None = None
    render_settings: dict | None = None
