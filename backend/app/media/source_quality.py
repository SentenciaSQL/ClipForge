"""Source-aware quality analysis and adaptive output recommendations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.media.aspect import ASPECT_PRESETS, _even, dimensions_for_aspect, ratio_string
from app.media.metadata import VideoMetadata, extract_metadata

QualityTier = Literal["very_low", "low", "medium", "high", "ultra"]
ReframeHint = Literal[
    "smart_crop",
    "center_crop",
    "blurred_bg",
    "solid_bg",
    "original",
    "manual",
]


@dataclass
class CropQualityImpact:
    crop_width: int
    crop_height: int
    retained_area_ratio: float
    linear_upscale: float
    severe: bool
    message: str


@dataclass
class SourceQualityAssessment:
    width: int
    height: int
    aspect_ratio: str
    fps: float | None
    video_codec: str | None
    audio_codec: str | None
    bitrate: int | None
    pixel_format: str | None
    color_range: str | None
    color_space: str | None
    color_transfer: str | None
    color_primaries: str | None
    rotation: int
    display_width: int
    display_height: int
    tier: QualityTier
    tier_label: str
    summary: str
    limitations: list[str] = field(default_factory=list)
    recommendations: dict[str, Any] = field(default_factory=dict)
    crop_impact: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rotation_degrees(stream: dict[str, Any], raw: dict[str, Any]) -> int:
    tags = stream.get("tags") or {}
    for key in ("rotate", "ROTATE"):
        if key in tags:
            try:
                return int(float(tags[key])) % 360
            except (TypeError, ValueError):
                pass
    for side_data in stream.get("side_data_list") or []:
        if side_data.get("side_data_type") in {"Display Matrix", "Display matrix"}:
            try:
                return int(float(side_data.get("rotation", 0))) % 360
            except (TypeError, ValueError):
                continue
    # Rare: format-level tags
    fmt_tags = (raw.get("format") or {}).get("tags") or {}
    if "rotate" in fmt_tags:
        try:
            return int(float(fmt_tags["rotate"])) % 360
        except (TypeError, ValueError):
            pass
    return 0


def display_dimensions(width: int, height: int, rotation: int) -> tuple[int, int]:
    if rotation in {90, 270, -90, -270}:
        return height, width
    return width, height


def quality_tier(width: int, height: int) -> tuple[QualityTier, str]:
    short = min(width, height)
    long = max(width, height)
    pixels = width * height
    if short < 480 or pixels < 480 * 640:
        return "very_low", "Very low resolution"
    if short < 720 or pixels < 720 * 1280:
        return "low", "Low resolution"
    if short < 1080 or pixels < 1080 * 1920:
        return "medium", "Medium resolution"
    if short < 1440 or long < 2560:
        return "high", "High resolution"
    return "ultra", "Ultra / 4K-class resolution"


def crop_window_for_aspect(
    source_width: int,
    source_height: int,
    aspect_key: str,
) -> tuple[int, int]:
    """Largest centered crop of source that matches the target aspect."""
    preset = ASPECT_PRESETS.get(aspect_key)
    if not preset or preset.key == "custom" or not preset.ratio_w:
        return source_width, source_height
    target = preset.ratio_w / preset.ratio_h
    src_w = max(1, source_width)
    src_h = max(1, source_height)
    crop_h = src_h
    crop_w = int(round(crop_h * target))
    if crop_w > src_w:
        crop_w = src_w
        crop_h = int(round(crop_w / target))
    return max(2, crop_w), max(2, crop_h)


def analyze_crop_impact(
    source_width: int,
    source_height: int,
    *,
    aspect_key: str,
    output_width: int,
    output_height: int,
) -> CropQualityImpact:
    crop_w, crop_h = crop_window_for_aspect(source_width, source_height, aspect_key)
    src_area = max(1, source_width * source_height)
    retained = (crop_w * crop_h) / src_area
    linear = max(output_width / max(1, crop_w), output_height / max(1, crop_h))
    severe = retained < 0.55 or linear > 2.0
    message = (
        f"A {aspect_key} crop uses ~{crop_w}x{crop_h} of the {source_width}x{source_height} source "
        f"(keeps {retained:.0%} of pixels). Scaling to {output_width}x{output_height} is "
        f"~{linear:.1f}× linear upscale."
    )
    return CropQualityImpact(
        crop_width=crop_w,
        crop_height=crop_h,
        retained_area_ratio=round(retained, 4),
        linear_upscale=round(linear, 3),
        severe=severe,
        message=message,
    )


def recommend_canvas(
    display_width: int,
    display_height: int,
    *,
    aspect_key: str = "9:16",
    allow_upscale: bool = False,
    prefer_label: str | None = None,
) -> tuple[int, int, str]:
    """
    Pick an output canvas that respects source detail.

    - Fit/blur-friendly: canvas short side limited by source short side unless upscaling allowed.
    - Labels: native / 480p / 720p / 1080p / …
    """
    src_short = min(display_width, display_height)
    src_long = max(display_width, display_height)

    # Preferred platform ceilings by source class.
    if src_short < 480:
        max_short = src_short if not allow_upscale else min(720, max(src_short, 640))
        label = "native"
    elif src_short < 720:
        max_short = 720 if allow_upscale else src_short
        label = "720p" if allow_upscale or src_short >= 720 else "native"
    elif src_short < 1080:
        max_short = 1080 if allow_upscale else min(1080, src_short)
        label = "1080p" if max_short >= 1080 else "720p"
    elif src_short < 1440:
        max_short = 1080 if not allow_upscale else min(1440, src_short)
        label = "1080p" if max_short <= 1080 else "1440p"
    else:
        max_short = 1080 if not allow_upscale else min(2160, src_short)
        label = {1080: "1080p", 1440: "1440p", 2160: "2160p"}.get(max_short, "1080p")
        if max_short not in {1080, 1440, 2160}:
            label = "native"

    if prefer_label and prefer_label in {"480p", "720p", "1080p", "1440p", "2160p"}:
        preferred = {"480p": 480, "720p": 720, "1080p": 1080, "1440p": 1440, "2160p": 2160}[prefer_label]
        if allow_upscale or preferred <= src_short + 8:
            max_short = preferred
            label = prefer_label
        else:
            label = "native" if max_short == src_short else label

    if aspect_key == "custom":
        return _even(display_width), _even(display_height), "custom"

    preset = ASPECT_PRESETS.get(aspect_key) or ASPECT_PRESETS["9:16"]
    if not preset.ratio_w:
        return _even(display_width), _even(display_height), label

    # Build canvas from short side along the shorter axis of the target aspect.
    if preset.ratio_w <= preset.ratio_h:
        width = max_short
        height = int(round(width * preset.ratio_h / preset.ratio_w))
    else:
        height = max_short
        width = int(round(height * preset.ratio_w / preset.ratio_h))

    # Never invent a canvas larger than ~source long edge unless upscaling.
    if not allow_upscale:
        width = min(width, max(src_long, src_short))
        height = min(height, max(int(round(src_long * preset.ratio_h / preset.ratio_w)), src_short * 2))
        # Re-sync aspect after clamping.
        if preset.ratio_w <= preset.ratio_h:
            height = int(round(width * preset.ratio_h / preset.ratio_w))
        else:
            width = int(round(height * preset.ratio_w / preset.ratio_h))

    return _even(width), _even(height), label


def recommend_reframe_mode(
    display_width: int,
    display_height: int,
    *,
    aspect_key: str = "9:16",
    content_hint: str | None = None,
) -> tuple[ReframeHint, str]:
    preset = ASPECT_PRESETS.get(aspect_key) or ASPECT_PRESETS["9:16"]
    if not preset.ratio_w:
        return "original", "Custom aspect — keep original framing"
    target = preset.ratio_w / preset.ratio_h
    source = display_width / max(1, display_height)
    impact = analyze_crop_impact(
        display_width,
        display_height,
        aspect_key=aspect_key,
        output_width=preset.default_width,
        output_height=preset.default_height,
    )
    hint = (content_hint or "").lower()
    if hint in {"gaming", "tutorial", "educational"}:
        return "blurred_bg", "Screen / instructional content — keep full frame with blurred sides"
    if hint in {"podcast", "interview"} and impact.retained_area_ratio >= 0.45:
        return "smart_crop", "Talking-head content — smart crop when faces are available"
    # Landscape → strong vertical: crop throws away most of the frame.
    if source > 1.15 and target < 0.9 and impact.retained_area_ratio < 0.55:
        return (
            "blurred_bg",
            "Landscape source into vertical canvas — blurred background preserves the full frame",
        )
    if abs(source - target) < 0.08:
        return "original", "Source aspect already close to target — pad/fit without cropping"
    if impact.severe:
        return "blurred_bg", impact.message
    return "smart_crop", "Crop is acceptable; smart crop will follow subjects when present"


def assess_source_quality(
    path: Path | str | None = None,
    *,
    metadata: VideoMetadata | None = None,
    width: int | None = None,
    height: int | None = None,
    fps: float | None = None,
    video_codec: str | None = None,
    audio_codec: str | None = None,
    bitrate: int | None = None,
    aspect_key: str = "9:16",
    allow_upscale: bool = False,
    content_hint: str | None = None,
) -> SourceQualityAssessment:
    meta = metadata
    if meta is None and path is not None:
        meta = extract_metadata(path)

    stream = (meta.video_streams[0] if meta and meta.video_streams else {}) or {}
    raw = meta.raw if meta else {}
    src_w = int(width or (meta.width if meta else 0) or stream.get("width") or 0)
    src_h = int(height or (meta.height if meta else 0) or stream.get("height") or 0)
    if src_w <= 0 or src_h <= 0:
        src_w, src_h = 1920, 1080

    rotation = _rotation_degrees(stream, raw)
    disp_w, disp_h = display_dimensions(src_w, src_h, rotation)
    tier, tier_label = quality_tier(disp_w, disp_h)
    fps_val = fps if fps is not None else (meta.fps if meta else None)
    codec = video_codec or (meta.video_codec if meta else None)
    a_codec = audio_codec or (meta.audio_codec if meta else None)
    br = bitrate if bitrate is not None else (meta.bitrate if meta else None)

    canvas_w, canvas_h, res_label = recommend_canvas(
        disp_w,
        disp_h,
        aspect_key=aspect_key,
        allow_upscale=allow_upscale,
    )
    reframe_mode, reframe_reason = recommend_reframe_mode(
        disp_w,
        disp_h,
        aspect_key=aspect_key,
        content_hint=content_hint,
    )
    crop = analyze_crop_impact(
        disp_w,
        disp_h,
        aspect_key=aspect_key,
        output_width=canvas_w,
        output_height=canvas_h,
    )

    limitations: list[str] = []
    warnings: list[str] = []
    if tier in {"very_low", "low"}:
        limitations.append(
            "Source detail is limited. Increasing the canvas size will not invent missing pixels."
        )
    if crop.severe and reframe_mode in {"smart_crop", "center_crop", "manual"}:
        warnings.append(crop.message)
    if not allow_upscale and (canvas_w * canvas_h) > (disp_w * disp_h) * 1.05:
        warnings.append(
            f"Recommended canvas {canvas_w}x{canvas_h} still exceeds source pixels; "
            "prefer blurred/fit modes or enable explicit upscaling."
        )
    if rotation:
        limitations.append(f"Rotation metadata detected ({rotation}°); display size uses upright frame.")

    native_dims = dimensions_for_aspect(aspect_key, resolution_label="1080p")
    if not allow_upscale and (native_dims[0] > canvas_w or native_dims[1] > canvas_h):
        warnings.append(
            f"Default 1080p canvas ({native_dims[0]}x{native_dims[1]}) exceeds what this source can support. "
            f"Recommended canvas: {canvas_w}x{canvas_h} ({res_label})."
        )

    recommendations = {
        "aspect_ratio": aspect_key,
        "resolution_label": res_label if res_label in {"480p", "720p", "1080p", "1440p", "2160p"} else "custom",
        "width": canvas_w,
        "height": canvas_h,
        "reframe_mode": reframe_mode,
        "reframe_reason": reframe_reason,
        "quality_preset": "high" if tier in {"very_low", "low", "medium"} else "balanced",
        "codec": "h264",
        "encoder": "auto",
        "preserve_source_fps": True,
        "allow_upscale": allow_upscale,
        "ai_upscale": False,
        "foreground_policy": "preserve_original_proportions",
        "notes": [
            f"Native display size: {disp_w}x{disp_h}",
            f"Output canvas: {canvas_w}x{canvas_h} ({res_label})",
            f"Effective crop (if cropping): {crop.crop_width}x{crop.crop_height}",
            reframe_reason,
        ],
    }

    summary = (
        f"Source {disp_w}x{disp_h} ({ratio_string(disp_w, disp_h)}) — {tier_label}. "
        f"Recommend {canvas_w}x{canvas_h} canvas with {reframe_mode.replace('_', ' ')}."
    )

    return SourceQualityAssessment(
        width=src_w,
        height=src_h,
        aspect_ratio=ratio_string(disp_w, disp_h),
        fps=fps_val,
        video_codec=codec,
        audio_codec=a_codec,
        bitrate=br,
        pixel_format=stream.get("pix_fmt"),
        color_range=stream.get("color_range"),
        color_space=stream.get("color_space"),
        color_transfer=stream.get("color_transfer"),
        color_primaries=stream.get("color_primaries"),
        rotation=rotation,
        display_width=disp_w,
        display_height=disp_h,
        tier=tier,
        tier_label=tier_label,
        summary=summary,
        limitations=limitations,
        recommendations=recommendations,
        crop_impact=asdict(crop),
        warnings=warnings,
    )
