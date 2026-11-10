"""Diarization request/response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class DiarizeRequest(BaseModel):
    engine: Literal["auto", "local", "pyannote"] | None = None
    max_speakers: int | None = Field(default=None, ge=1, le=8)


class SpeakerOut(ORMModel):
    id: str
    video_id: str
    label: str
    display_name: str | None
    metadata_json: dict[str, Any] | None = None


class SpeakerRenameRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)
