"""Video metadata extraction via FFprobe."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.media.ffmpeg import ffprobe_json


@dataclass
class VideoMetadata:
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    video_codec: str | None
    audio_codec: str | None
    aspect_ratio: str | None
    bitrate: int | None
    file_size_bytes: int
    format_name: str | None
    video_streams: list[dict[str, Any]]
    audio_streams: list[dict[str, Any]]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_fps(stream: dict[str, Any]) -> float | None:
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = stream.get(key)
        if not value or value in {"0/0", "N/A"}:
            continue
        try:
            return float(Fraction(value))
        except (ValueError, ZeroDivisionError):
            continue
    return None


def _aspect_ratio(width: int | None, height: int | None, stream: dict[str, Any]) -> str | None:
    display = stream.get("display_aspect_ratio")
    if display and display not in {"0:1", "N/A"}:
        return display
    if width and height:
        ratio = Fraction(width, height).limit_denominator(100)
        return f"{ratio.numerator}:{ratio.denominator}"
    return None


def extract_metadata(path: Path | str) -> VideoMetadata:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")

    probe = ffprobe_json(file_path)
    streams = probe.get("streams", [])
    fmt = probe.get("format", {})

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    primary_video = video_streams[0] if video_streams else {}
    primary_audio = audio_streams[0] if audio_streams else {}

    width = primary_video.get("width")
    height = primary_video.get("height")
    duration = None
    if fmt.get("duration"):
        try:
            duration = float(fmt["duration"])
        except (TypeError, ValueError):
            duration = None
    if duration is None and primary_video.get("duration"):
        try:
            duration = float(primary_video["duration"])
        except (TypeError, ValueError):
            duration = None

    bitrate = None
    if fmt.get("bit_rate"):
        try:
            bitrate = int(fmt["bit_rate"])
        except (TypeError, ValueError):
            bitrate = None

    size = file_path.stat().st_size
    if fmt.get("size"):
        try:
            size = int(fmt["size"])
        except (TypeError, ValueError):
            pass

    return VideoMetadata(
        duration_seconds=duration,
        width=int(width) if width else None,
        height=int(height) if height else None,
        fps=_parse_fps(primary_video),
        video_codec=primary_video.get("codec_name"),
        audio_codec=primary_audio.get("codec_name"),
        aspect_ratio=_aspect_ratio(
            int(width) if width else None,
            int(height) if height else None,
            primary_video,
        ),
        bitrate=bitrate,
        file_size_bytes=size,
        format_name=fmt.get("format_name"),
        video_streams=video_streams,
        audio_streams=audio_streams,
        raw=probe,
    )
