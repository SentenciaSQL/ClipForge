"""FFmpeg / FFprobe command helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.core.hardware import detect_hardware
from app.core.logging import get_logger

logger = get_logger(__name__)


class FFmpegError(RuntimeError):
    """Raised when an FFmpeg or FFprobe invocation fails."""


def get_ffmpeg() -> str:
    profile = detect_hardware()
    if not profile.ffmpeg_path:
        raise FFmpegError(
            "FFmpeg is not available. Install FFmpeg and configure AVC_FFMPEG_PATH if needed."
        )
    return profile.ffmpeg_path


def get_ffprobe() -> str:
    profile = detect_hardware()
    if not profile.ffprobe_path:
        raise FFmpegError(
            "FFprobe is not available. Install FFmpeg and configure AVC_FFPROBE_PATH if needed."
        )
    return profile.ffprobe_path


def run_command(args: list[str], timeout: int | None = 300) -> subprocess.CompletedProcess[str]:
    logger.debug("Running command: %s", " ".join(args))
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FFmpegError(f"Executable not found: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"Command timed out after {timeout}s: {' '.join(args)}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise FFmpegError(f"Command failed ({result.returncode}): {stderr[:2000]}")
    return result


def ffprobe_json(path: Path | str) -> dict[str, Any]:
    probe = get_ffprobe()
    result = run_command(
        [
            probe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout=60,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FFmpegError(f"Invalid FFprobe JSON for {path}") from exc


def extract_audio_wav(video_path: Path, output_path: Path, sample_rate: int = 16000) -> Path:
    """Extract mono WAV audio suitable for Faster-Whisper."""
    ffmpeg = get_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            str(output_path),
        ],
        timeout=600,
    )
    return output_path
