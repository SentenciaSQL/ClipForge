"""Audio track configuration helpers (persisted on Clip / AudioTrack)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TrackType = Literal["original", "music", "replacement", "voiceover"]


class AudioTrackConfig(BaseModel):
    track_type: TrackType
    label: str = "Track"
    source_path: str | None = None
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    muted: bool = False
    start_seconds: float = 0.0
    end_seconds: float | None = None
    offset_seconds: float = 0.0
    fade_in_seconds: float = 0.0
    fade_out_seconds: float = 0.0
    loop: bool = False
    ducking_enabled: bool = False
    metadata: dict[str, Any] | None = None


def default_original_track() -> AudioTrackConfig:
    return AudioTrackConfig(track_type="original", label="Original", volume=1.0)


def tracks_to_json(tracks: list[AudioTrackConfig]) -> list[dict[str, Any]]:
    return [track.model_dump() for track in tracks]
