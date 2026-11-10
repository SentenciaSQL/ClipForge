"""Audio metadata and stream analysis via FFprobe."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.media.ffmpeg import ffprobe_json


@dataclass
class AudioStreamInfo:
    codec: str | None
    sample_rate: int | None
    channels: int | None
    channel_layout: str | None
    bitrate: int | None
    duration_seconds: float | None
    language: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_audio(path: Path | str) -> list[AudioStreamInfo]:
    probe = ffprobe_json(path)
    streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
    format_duration = None
    if probe.get("format", {}).get("duration"):
        try:
            format_duration = float(probe["format"]["duration"])
        except (TypeError, ValueError):
            format_duration = None

    results: list[AudioStreamInfo] = []
    for stream in streams:
        duration = format_duration
        if stream.get("duration"):
            try:
                duration = float(stream["duration"])
            except (TypeError, ValueError):
                pass
        bitrate = None
        if stream.get("bit_rate"):
            try:
                bitrate = int(stream["bit_rate"])
            except (TypeError, ValueError):
                bitrate = None
        sample_rate = None
        if stream.get("sample_rate"):
            try:
                sample_rate = int(stream["sample_rate"])
            except (TypeError, ValueError):
                sample_rate = None
        channels = stream.get("channels")
        tags = stream.get("tags") or {}
        results.append(
            AudioStreamInfo(
                codec=stream.get("codec_name"),
                sample_rate=sample_rate,
                channels=int(channels) if channels is not None else None,
                channel_layout=stream.get("channel_layout"),
                bitrate=bitrate,
                duration_seconds=duration,
                language=tags.get("language"),
            )
        )
    return results
