"""Persist and validate pre-generation configuration for source videos."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import Clip, GenerationProfile, SourceVideo, SubtitlePreset
from app.media.aspect import validate_dimensions
from app.schemas.generation_config import (
    GenerationConfiguration,
    GenerationConfigurationOut,
    GenerationProfileIn,
    GenerationProfileOut,
)

logger = get_logger(__name__)


def default_generation_configuration() -> GenerationConfiguration:
    return GenerationConfiguration()


def get_generation_configuration(video: SourceVideo) -> GenerationConfiguration:
    raw = video.generation_config_json if isinstance(video.generation_config_json, dict) else {}
    if not raw:
        return default_generation_configuration()
    try:
        return GenerationConfiguration.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invalid generation config for video %s: %s", video.id, exc)
        return default_generation_configuration()


def validate_generation_configuration(
    config: GenerationConfiguration,
    *,
    video: SourceVideo,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if config.duration.min_duration > config.duration.max_duration:
        errors.append("Minimum duration cannot exceed maximum duration")
    duration = float(video.duration_seconds or 0)
    if duration > 0 and config.duration.min_duration > duration:
        errors.append(
            f"Minimum clip duration ({config.duration.min_duration}s) exceeds video length ({duration:.1f}s)"
        )
    if duration > 0 and config.duration.max_duration > duration:
        warnings.append(
            f"Maximum clip duration ({config.duration.max_duration}s) exceeds video length; it will be clamped"
        )
    dim = validate_dimensions(
        config.video.width,
        config.video.height,
        source_width=video.width,
        source_height=video.height,
        allow_upscale=bool(config.video.allow_upscale),
        reframe_mode=config.reframe.mode,
    )
    errors.extend(dim.get("errors") or [])
    warnings.extend(dim.get("warnings") or [])
    return {"ok": not errors, "errors": errors, "warnings": warnings, **dim}


def apply_adaptive_quality(
    config: GenerationConfiguration,
    *,
    video: SourceVideo,
    force: bool = False,
) -> GenerationConfiguration:
    """Apply source-aware canvas/reframe recommendations when auto_quality is on."""
    if not config.video.auto_quality and not force:
        return config
    from app.media.source_quality import assess_source_quality

    assessment = assess_source_quality(
        path=video.stored_path if video.stored_path else None,
        width=video.width,
        height=video.height,
        fps=video.fps,
        video_codec=video.video_codec,
        audio_codec=video.audio_codec,
        bitrate=video.bitrate,
        aspect_key=config.video.aspect_ratio,
        allow_upscale=bool(config.video.allow_upscale),
        content_hint=config.analysis.content_category,
    )
    rec = assessment.recommendations or {}
    data = config.model_dump()
    data["video"]["width"] = int(rec.get("width") or config.video.width)
    data["video"]["height"] = int(rec.get("height") or config.video.height)
    label = rec.get("resolution_label") or config.video.resolution_label
    data["video"]["resolution_label"] = label if label in {"480p", "720p", "1080p", "1440p", "2160p", "custom"} else "custom"
    data["video"]["quality_preset"] = rec.get("quality_preset") or config.video.quality_preset
    data["video"]["preserve_source_fps"] = True
    data["video"]["fps"] = None
    data["reframe"]["mode"] = rec.get("reframe_mode") or config.reframe.mode
    if data["reframe"]["mode"] in {"blurred_bg", "original", "solid_bg", "fit_original"}:
        data["reframe"]["enable_face_detection"] = False
    data["video"]["auto_quality"] = config.video.auto_quality
    data["_quality_assessment"] = assessment.to_dict()  # stripped by model_validate if unknown — keep via warnings path
    adapted = GenerationConfiguration.model_validate({k: v for k, v in data.items() if not k.startswith("_")})
    return adapted


def build_summary(config: GenerationConfiguration) -> list[str]:
    auto = "Automatic" if config.duration.auto_clip_count else str(config.duration.clip_count)
    subs = "Enabled" if config.subtitles.enabled else "Disabled"
    fps = "Preserve source" if config.video.preserve_source_fps else str(config.video.fps or 30)
    lang = config.analysis.language or "Automatic"
    upscale = "Allowed" if config.video.allow_upscale else "Disabled"
    return [
        f"Clip duration: {config.duration.min_duration}–{config.duration.max_duration} seconds",
        f"Number of clips: {auto}",
        f"Subtitles: {subs}",
        f"Subtitle style: {config.subtitles.preset_slug}",
        f"Aspect ratio: {config.video.aspect_ratio}",
        f"Resolution: {config.video.resolution_label} ({config.video.width}x{config.video.height})",
        f"Quality preset: {config.video.quality_preset}",
        f"Encoder: {config.video.encoder} / {config.video.codec}",
        f"Upscaling: {upscale}",
        f"Auto quality: {'On' if config.video.auto_quality else 'Off'}",
        f"FPS: {fps}",
        f"Reframing: {config.reframe.mode}",
        f"Audio: {config.audio.mode}",
        f"AI language: {lang}",
        f"Whisper model: {config.analysis.whisper_model}",
        f"Content category: {config.analysis.content_category}",
        f"Sensitivity: {config.analysis.sensitivity}",
    ]


def save_generation_configuration(
    db: Session,
    video: SourceVideo,
    config: GenerationConfiguration,
    *,
    apply_adaptive: bool = False,
) -> GenerationConfiguration:
    # Never silently overwrite user overrides on ordinary saves.
    # Adaptive canvas/reframe is applied only when explicitly requested
    # (apply-adaptive endpoint / first empty load) or apply_adaptive=True.
    if apply_adaptive and config.video.auto_quality:
        config = apply_adaptive_quality(config, video=video, force=True)
    video.generation_config_json = config.model_dump()
    video.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(video)
    return config


def configuration_out(db: Session, video: SourceVideo) -> GenerationConfigurationOut:
    from app.media.source_quality import assess_source_quality

    config = get_generation_configuration(video)
    # Fresh videos with empty config still get adaptive defaults when auto_quality is on.
    if not video.generation_config_json and config.video.auto_quality:
        config = apply_adaptive_quality(config, video=video)
        save_generation_configuration(db, video, config, apply_adaptive=False)

    # Probe recommendations against the *current* canvas.
    quality = assess_source_quality(
        path=video.stored_path if video.stored_path else None,
        width=video.width,
        height=video.height,
        fps=video.fps,
        video_codec=video.video_codec,
        audio_codec=video.audio_codec,
        bitrate=video.bitrate,
        aspect_key=config.video.aspect_ratio,
        allow_upscale=bool(config.video.allow_upscale),
        content_hint=config.analysis.content_category,
        requested_width=config.video.width,
        requested_height=config.video.height,
    )

    # If auto_quality is on and the saved canvas is still too large, apply the
    # recommendation automatically so exports match source detail.
    rec = quality.recommendations or {}
    rec_w = int(rec.get("width") or 0)
    rec_h = int(rec.get("height") or 0)
    if (
        config.video.auto_quality
        and not config.video.allow_upscale
        and rec_w
        and rec_h
        and (config.video.width > rec_w + 2 or config.video.height > rec_h + 2)
    ):
        config = apply_adaptive_quality(config, video=video, force=True)
        save_generation_configuration(db, video, config, apply_adaptive=False)
        quality = assess_source_quality(
            path=video.stored_path if video.stored_path else None,
            width=video.width,
            height=video.height,
            fps=video.fps,
            video_codec=video.video_codec,
            audio_codec=video.audio_codec,
            bitrate=video.bitrate,
            aspect_key=config.video.aspect_ratio,
            allow_upscale=bool(config.video.allow_upscale),
            content_hint=config.analysis.content_category,
            requested_width=config.video.width,
            requested_height=config.video.height,
        )

    validation = validate_generation_configuration(config, video=video)
    # Merge quality warnings into validation warnings (do not fail the request).
    for warn in quality.warnings:
        if warn not in (validation.get("warnings") or []):
            validation.setdefault("warnings", []).append(warn)
    return GenerationConfigurationOut(
        video_id=video.id,
        configuration=config,
        validation=validation,
        summary=build_summary(config),
        source_quality=quality.to_dict(),
    )


def apply_generation_config_to_clips(
    db: Session,
    video: SourceVideo,
    clips: list[Clip],
    config: GenerationConfiguration | None = None,
) -> None:
    """Stamp each new clip with the generation configuration as its render_settings."""
    cfg = config or get_generation_configuration(video)
    clip_cfg = cfg.to_clip_configuration()
    preset = db.scalar(select(SubtitlePreset).where(SubtitlePreset.slug == cfg.subtitles.preset_slug))
    for clip in clips:
        clip.reframing_mode = cfg.reframe.mode
        if preset:
            clip.subtitle_preset_id = preset.id
        clip.audio_config = {
            **(clip.audio_config or {}),
            "generation_audio_mode": cfg.audio.mode,
        }
        # Preserve rank if present.
        rank = (clip.render_settings or {}).get("rank")
        dump = clip_cfg.model_dump()
        if rank is not None:
            dump["rank"] = rank
        dump["inherited_from_generation"] = True
        clip.render_settings = dump
    db.commit()


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "profile"


def _profile_out(row: GenerationProfile) -> GenerationProfileOut:
    return GenerationProfileOut(
        id=row.id,
        name=row.name,
        slug=row.slug,
        description=row.description,
        config_json=dict(row.config_json or {}),
        is_builtin=bool(row.is_builtin),
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def builtin_generation_profiles() -> list[dict[str, Any]]:
    def make(**overrides: Any) -> dict[str, Any]:
        base = default_generation_configuration()
        data = base.model_dump()
        for key, value in overrides.items():
            if key in data and isinstance(data[key], dict) and isinstance(value, dict):
                data[key].update(value)
            else:
                data[key] = value
        return GenerationConfiguration.model_validate(data).model_dump()

    return [
        {
            "name": "TikTok / Reels / Shorts",
            "slug": "tiktok-reels-shorts",
            "description": "Vertical 9:16 with subtitles and smart crop",
            "config_json": make(
                video={
                    "aspect_ratio": "9:16",
                    "resolution_label": "1080p",
                    "width": 1080,
                    "height": 1920,
                    "fps": None,
                    "preserve_source_fps": True,
                    "auto_quality": True,
                    "allow_upscale": False,
                    "quality_preset": "high",
                },
                reframe={"mode": "auto", "enable_face_detection": True},
                subtitles={"enabled": True, "preset_slug": "tiktok"},
                analysis={"content_category": "general", "sensitivity": "medium"},
            ),
        },
        {
            "name": "YouTube Landscape",
            "slug": "youtube-landscape",
            "description": "16:9 landscape clips",
            "config_json": make(
                video={
                    "aspect_ratio": "16:9",
                    "resolution_label": "1080p",
                    "width": 1920,
                    "height": 1080,
                    "preserve_source_fps": True,
                    "auto_quality": True,
                    "allow_upscale": False,
                },
                reframe={"mode": "original", "enable_face_detection": False},
                subtitles={"enabled": True, "preset_slug": "professional"},
            ),
        },
        {
            "name": "Instagram Square",
            "slug": "instagram-square",
            "description": "1:1 square posts",
            "config_json": make(
                video={
                    "aspect_ratio": "1:1",
                    "resolution_label": "1080p",
                    "width": 1080,
                    "height": 1080,
                    "auto_quality": True,
                    "allow_upscale": False,
                },
                reframe={"mode": "auto"},
                subtitles={"enabled": True, "preset_slug": "minimal"},
            ),
        },
        {
            "name": "Podcast Clips",
            "slug": "podcast-clips",
            "description": "Talking-head podcast vertical clips",
            "config_json": make(
                video={"aspect_ratio": "9:16", "resolution_label": "1080p", "auto_quality": True, "allow_upscale": False},
                reframe={"mode": "podcast", "enable_face_detection": True},
                subtitles={"enabled": True, "preset_slug": "podcast"},
                analysis={"content_category": "podcast", "sensitivity": "high"},
                duration={"min_duration": 15, "max_duration": 30, "clip_count": 6, "auto_clip_count": True},
            ),
        },
        {
            "name": "Gaming Clips",
            "slug": "gaming-clips",
            "description": "Screen content with blurred sides, no face tracking",
            "config_json": make(
                video={"aspect_ratio": "9:16", "resolution_label": "1080p", "auto_quality": True, "allow_upscale": False},
                reframe={"mode": "gaming", "enable_face_detection": False},
                subtitles={"enabled": True, "preset_slug": "gaming"},
                analysis={"content_category": "gaming", "sensitivity": "medium"},
            ),
        },
        {
            "name": "Custom Profile",
            "slug": "custom-profile",
            "description": "Editable starting point — duplicate and save your own variants",
            "config_json": make(),
        },
    ]


def seed_generation_profiles(db: Session) -> None:
    for item in builtin_generation_profiles():
        existing = db.scalar(select(GenerationProfile).where(GenerationProfile.slug == item["slug"]))
        if existing:
            existing.name = item["name"]
            existing.description = item["description"]
            existing.config_json = item["config_json"]
            existing.is_builtin = True
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(
                GenerationProfile(
                    name=item["name"],
                    slug=item["slug"],
                    description=item["description"],
                    config_json=item["config_json"],
                    is_builtin=True,
                )
            )
    db.commit()
    logger.info("Generation profiles seeded")


def list_generation_profiles(db: Session) -> list[GenerationProfileOut]:
    rows = list(db.scalars(select(GenerationProfile).order_by(GenerationProfile.name.asc())).all())
    return [_profile_out(row) for row in rows]


def create_generation_profile(db: Session, payload: GenerationProfileIn) -> GenerationProfileOut:
    slug = payload.slug or _slugify(payload.name)
    if db.scalar(select(GenerationProfile).where(GenerationProfile.slug == slug)):
        raise ValueError(f"Profile slug already exists: {slug}")
    row = GenerationProfile(
        name=payload.name,
        slug=slug,
        description=payload.description,
        config_json=payload.config_json.model_dump(),
        is_builtin=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _profile_out(row)


def update_generation_profile(
    db: Session,
    profile_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    config_json: GenerationConfiguration | None = None,
) -> GenerationProfileOut:
    row = get_generation_profile(db, profile_id)
    if row.is_builtin and (name is not None or config_json is not None):
        # Built-ins can only have description tweaked via seed; block edits from API.
        raise PermissionError("Built-in profiles cannot be edited; duplicate them instead")
    if name is not None:
        row.name = name
    if description is not None:
        row.description = description
    if config_json is not None:
        row.config_json = config_json.model_dump()
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _profile_out(row)


def duplicate_generation_profile(db: Session, profile_id: str, *, name: str | None = None) -> GenerationProfileOut:
    source = get_generation_profile(db, profile_id)
    base_name = name or f"{source.name} Copy"
    slug = _slugify(base_name)
    existing_slug = db.scalar(select(GenerationProfile).where(GenerationProfile.slug == slug))
    if existing_slug:
        slug = f"{slug}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    row = GenerationProfile(
        name=base_name,
        slug=slug,
        description=source.description,
        config_json=dict(source.config_json or {}),
        is_builtin=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _profile_out(row)


def delete_generation_profile(db: Session, profile_id: str) -> None:
    row = db.get(GenerationProfile, profile_id)
    if not row:
        raise LookupError("Generation profile not found")
    if row.is_builtin:
        raise PermissionError("Built-in profiles cannot be deleted")
    db.delete(row)
    db.commit()


def get_generation_profile(db: Session, profile_id: str) -> GenerationProfile:
    row = db.get(GenerationProfile, profile_id)
    if not row:
        raise LookupError("Generation profile not found")
    return row
