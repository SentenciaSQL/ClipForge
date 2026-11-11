"""Aspect ratio presets, resolution helpers, and validation."""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from typing import Any


@dataclass(frozen=True)
class AspectPreset:
    key: str
    label: str
    ratio_w: int
    ratio_h: int
    recommended_use: str
    default_width: int
    default_height: int


ASPECT_PRESETS: dict[str, AspectPreset] = {
    "9:16": AspectPreset("9:16", "Vertical", 9, 16, "TikTok, Reels, Shorts", 1080, 1920),
    "1:1": AspectPreset("1:1", "Square", 1, 1, "Instagram posts", 1080, 1080),
    "16:9": AspectPreset("16:9", "Landscape", 16, 9, "YouTube, desktop", 1920, 1080),
    "4:3": AspectPreset("4:3", "Classic", 4, 3, "Traditional video", 1440, 1080),
    "4:5": AspectPreset("4:5", "Portrait", 4, 5, "Instagram feed", 1080, 1350),
    "21:9": AspectPreset("21:9", "Cinema", 21, 9, "Cinematic content", 2560, 1080),
    "custom": AspectPreset("custom", "Custom", 0, 0, "Custom projects", 1080, 1920),
}

RESOLUTION_PRESETS: dict[str, tuple[int, int] | None] = {
    "480p": None,  # derived from aspect
    "720p": None,
    "1080p": None,
    "1440p": None,
    "2160p": None,
    "custom": None,
}

_HEIGHT_FOR_LABEL = {
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "1440p": 1440,
    "2160p": 2160,
}


def list_aspect_presets() -> list[dict[str, Any]]:
    return [
        {
            "key": p.key,
            "label": p.label,
            "aspect_ratio": p.key,
            "recommended_use": p.recommended_use,
            "default_width": p.default_width,
            "default_height": p.default_height,
        }
        for p in ASPECT_PRESETS.values()
    ]


def ratio_string(width: int, height: int) -> str:
    w, h = max(1, width), max(1, height)
    g = gcd(w, h)
    return f"{w // g}:{h // g}"


def dimensions_for_aspect(
    aspect_key: str,
    *,
    resolution_label: str = "1080p",
    custom_width: int | None = None,
    custom_height: int | None = None,
) -> tuple[int, int]:
    if aspect_key == "custom" or resolution_label == "custom":
        width = int(custom_width or 1080)
        height = int(custom_height or 1920)
        return _even(width), _even(height)

    preset = ASPECT_PRESETS.get(aspect_key) or ASPECT_PRESETS["9:16"]
    if preset.key == "custom":
        return _even(int(custom_width or 1080)), _even(int(custom_height or 1920))

    scale = {
        "480p": 480 / 1080,
        "720p": 720 / 1080,
        "1080p": 1.0,
        "1440p": 1440 / 1080,
        "2160p": 2160 / 1080,
    }.get(resolution_label, 1.0)
    width = int(round(preset.default_width * scale))
    height = int(round(preset.default_height * scale))
    return _even(width), _even(height)


def _even(value: int) -> int:
    value = max(2, int(value))
    return value if value % 2 == 0 else value + 1


def validate_dimensions(
    width: int,
    height: int,
    *,
    source_width: int | None = None,
    source_height: int | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    if width < 16 or height < 16:
        errors.append("Output dimensions must be at least 16x16")
    if width > 7680 or height > 7680:
        errors.append("Output dimensions exceed 8K limits")
    if width % 2 or height % 2:
        warnings.append("Odd dimensions will be rounded to even values for yuv420p")
    if source_width and source_height:
        if width * height > source_width * source_height * 1.05:
            warnings.append(
                f"Selected output ({width}x{height}) exceeds source "
                f"({source_width}x{source_height}); upscaling is not recommended."
            )
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "aspect_ratio": ratio_string(width, height),
        "width": _even(width),
        "height": _even(height),
    }


def estimate_file_size_bytes(
    *,
    duration_seconds: float,
    width: int,
    height: int,
    fps: int,
    quality_preset: str = "balanced",
    audio_bitrate_kbps: int = 192,
) -> int:
    """Rough estimate for UI display (not exact)."""
    pixels = max(1, width * height)
    # Bits per pixel heuristic by quality.
    bpp = {"fast": 0.04, "balanced": 0.07, "high": 0.11, "custom": 0.08}.get(quality_preset, 0.07)
    video_bps = pixels * max(1, fps) * bpp
    audio_bps = audio_bitrate_kbps * 1000
    return int(max(1.0, duration_seconds) * (video_bps + audio_bps) / 8)
