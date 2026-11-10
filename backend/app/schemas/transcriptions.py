"""Transcription API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class WordOut(BaseModel):
    word: str
    start: float
    end: float
    confidence: float | None = None
    index: int = 0


class SegmentOut(BaseModel):
    id: int
    start: float
    end: float
    text: str
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    words: list[WordOut] = Field(default_factory=list)


class TranscriptionOut(ORMModel):
    id: str
    video_id: str
    language: str | None
    language_probability: float | None
    model_name: str
    full_text: str | None
    audio_path: str | None
    duration_seconds: float | None
    created_at: datetime
    segment_count: int = 0
    word_count: int = 0
    segments: list[SegmentOut] | None = None
    words: list[WordOut] | None = None
    meta: dict[str, Any] | None = None


class TranscribeRequest(BaseModel):
    language: str | None = Field(default=None, description="ISO code or null for auto-detect")
    whisper_model: str | None = None
    force: bool = Field(default=False, description="Ignore cached transcription and re-run")
