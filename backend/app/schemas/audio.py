"""Audio Studio request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

TrackType = Literal["original", "music", "replacement", "voiceover"]


class AudioTrackOut(ORMModel):
    id: str
    clip_id: str
    track_type: str
    label: str
    source_path: str | None
    volume: float
    muted: bool
    start_seconds: float
    end_seconds: float | None
    offset_seconds: float
    fade_in_seconds: float
    fade_out_seconds: float
    loop: bool
    ducking_enabled: bool
    metadata_json: dict[str, Any] | None = None
    created_at: datetime


class AudioTrackCreate(BaseModel):
    track_type: TrackType
    label: str | None = None
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    muted: bool = False
    offset_seconds: float = 0.0
    fade_in_seconds: float = Field(default=0.0, ge=0.0)
    fade_out_seconds: float = Field(default=0.0, ge=0.0)
    loop: bool = False
    ducking_enabled: bool = False


class AudioTrackUpdate(BaseModel):
    label: str | None = None
    volume: float | None = Field(default=None, ge=0.0, le=2.0)
    muted: bool | None = None
    offset_seconds: float | None = None
    fade_in_seconds: float | None = Field(default=None, ge=0.0)
    fade_out_seconds: float | None = Field(default=None, ge=0.0)
    loop: bool | None = None
    ducking_enabled: bool | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None


class AudioMixSettings(BaseModel):
    enable_loudnorm: bool = True
    enable_limiter: bool = True
    integrated_lufs: float = -14.0
    true_peak: float = -1.5
    lra: float = 11.0
    ducking_threshold: float = 0.05
    ducking_ratio: float = 6.0
    ducking_attack_ms: float = 20.0
    ducking_release_ms: float = 250.0
    preset_slug: str | None = None


class AudioStudioState(BaseModel):
    clip_id: str
    duration_seconds: float
    tracks: list[AudioTrackOut]
    mix_settings: AudioMixSettings
    audio_presets: list[dict[str, Any]] = Field(default_factory=list)


class ApplyAudioPresetRequest(BaseModel):
    preset_slug: str
