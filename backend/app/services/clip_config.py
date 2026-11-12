"""Per-clip configuration load/save/merge (versioned schema)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.database.models import Clip, SourceVideo, SubtitlePreset
from app.media.aspect import estimate_file_size_bytes, validate_dimensions
from app.schemas.clip_config import (
    CONFIG_SCHEMA_VERSION,
    ClipConfiguration,
    ClipConfigurationOut,
    ClipConfigurationPatch,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def default_configuration() -> ClipConfiguration:
    return ClipConfiguration()


def _migrate_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {})
    version = int(data.get("schema_version") or 0)
    if version < 1:
        # Lift legacy flat render_settings into v1 shape when possible.
        legacy = data
        migrated = default_configuration().model_dump()
        if "burn_subtitles" in legacy:
            migrated["subtitles"]["enabled"] = bool(legacy.get("burn_subtitles", True))
        if legacy.get("subtitle_preset"):
            migrated["subtitles"]["preset_slug"] = str(legacy["subtitle_preset"])
        if legacy.get("output_width") and legacy.get("output_height"):
            migrated["video"]["width"] = int(legacy["output_width"])
            migrated["video"]["height"] = int(legacy["output_height"])
            migrated["video"]["resolution_label"] = "custom"
            migrated["video"]["aspect_ratio"] = "custom"
        if legacy.get("reframe"):
            migrated["reframe"]["mode"] = str(legacy["reframe"])
        migrated["schema_version"] = CONFIG_SCHEMA_VERSION
        return migrated
    data["schema_version"] = CONFIG_SCHEMA_VERSION
    return data


def get_clip_configuration(db: Session, clip: Clip) -> ClipConfiguration:
    raw = _migrate_config(clip.render_settings if isinstance(clip.render_settings, dict) else {})
    # Keep reframing_mode column as source of truth when config lacks an explicit mode.
    try:
        cfg = ClipConfiguration.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invalid clip config for %s (%s); using defaults", clip.id, exc)
        cfg = default_configuration()
    if clip.reframing_mode and cfg.reframe.mode == "auto":
        # Prefer stored column only if config still defaulted.
        if not (clip.render_settings or {}).get("reframe"):
            cfg.reframe.mode = clip.reframing_mode  # type: ignore[assignment]
    if clip.subtitle_preset_id:
        preset = db.get(SubtitlePreset, clip.subtitle_preset_id)
        if preset and not (clip.render_settings or {}).get("subtitles"):
            cfg.subtitles.preset_slug = preset.slug
            style = dict(preset.config_json)
            cfg.subtitles.style.font_family = str(style.get("font_family") or cfg.subtitles.style.font_family)
            cfg.subtitles.style.font_size = int(style.get("font_size") or cfg.subtitles.style.font_size)
            cfg.subtitles.style.text_color = str(style.get("primary_color") or cfg.subtitles.style.text_color)
            cfg.subtitles.style.highlight_color = str(
                style.get("highlight_color") or cfg.subtitles.style.highlight_color
            )
    return cfg


def merge_configuration(base: ClipConfiguration, patch: ClipConfigurationPatch) -> ClipConfiguration:
    data = base.model_dump()
    updates = patch.model_dump(exclude_unset=True)
    for key in ("subtitles", "video", "reframe", "audio", "export"):
        if key in updates and updates[key] is not None:
            data[key] = updates[key]
    if "profile_id" in updates:
        data["profile_id"] = updates["profile_id"]
    return ClipConfiguration.model_validate(data)


def save_clip_configuration(db: Session, clip: Clip, config: ClipConfiguration) -> ClipConfiguration:
    clip.render_settings = config.model_dump()
    clip.reframing_mode = config.reframe.mode
    # Link subtitle preset id when slug matches a known preset.
    from sqlalchemy import select

    preset = db.scalar(select(SubtitlePreset).where(SubtitlePreset.slug == config.subtitles.preset_slug))
    if preset:
        clip.subtitle_preset_id = preset.id
    # Config edits invalidate prior renders but do not touch transcription.
    clip.status = "candidate"
    clip.output_path = None
    db.commit()
    db.refresh(clip)
    return config


def configuration_out(db: Session, clip: Clip) -> ClipConfigurationOut:
    video = db.get(SourceVideo, clip.video_id)
    cfg = get_clip_configuration(db, clip)
    validation = validate_dimensions(
        cfg.video.width,
        cfg.video.height,
        source_width=video.width if video else None,
        source_height=video.height if video else None,
        allow_upscale=bool(getattr(cfg.video, "allow_upscale", False)),
        reframe_mode=cfg.reframe.mode,
    )
    fps = cfg.video.fps or int(round(video.fps or 30)) if video else (cfg.video.fps or 30)
    if cfg.video.preserve_source_fps and video and video.fps:
        fps = int(round(video.fps))
    estimate = estimate_file_size_bytes(
        duration_seconds=float(clip.duration_seconds),
        width=cfg.video.width,
        height=cfg.video.height,
        fps=int(fps or 30),
        quality_preset=cfg.video.quality_preset,
        audio_bitrate_kbps=cfg.audio.bitrate_kbps,
    )
    cfg.warnings = list(validation.get("warnings") or [])
    return ClipConfigurationOut(
        clip_id=clip.id,
        configuration=cfg,
        source_width=video.width if video else None,
        source_height=video.height if video else None,
        source_fps=video.fps if video else None,
        estimated_file_size_bytes=estimate,
        validation=validation,
    )


def style_dict_from_config(config: ClipConfiguration) -> dict[str, Any]:
    """Map ClipConfiguration subtitle style → ASS generator preset dict."""
    style = config.subtitles.style
    animation = style.animation
    word_highlight = animation in {"word", "karaoke", "punch"}
    return {
        "slug": config.subtitles.preset_slug,
        "name": config.subtitles.preset_slug,
        "font_family": style.font_family,
        "font_size": style.font_size,
        "primary_color": style.text_color,
        "highlight_color": style.highlight_color,
        "outline_color": style.outline_color,
        "outline_width": style.outline_width,
        "shadow": style.shadow,
        "position": style.position if style.position != "custom" else "bottom",
        "max_lines": style.max_lines,
        "alignment": style.alignment,
        "word_highlight": word_highlight,
        "animation_preset": animation,
        "uppercase": bool(style.uppercase or style.all_caps_words),
        "bold": style.font_weight == "bold",
        "italic": bool(style.italic),
        "margin_h": style.margin_h,
        "max_chars_per_line": style.max_chars_per_line,
        "opacity": style.opacity,
        "custom_vertical": style.custom_vertical,
        "safe_area": style.safe_area,
        "box_enabled": bool(style.box_enabled),
        "box_color": style.box_color,
        "box_opacity": style.box_opacity,
        "letter_spacing": style.letter_spacing,
        "timing_offset_seconds": float(config.subtitles.timing_offset_seconds or 0.0),
    }
