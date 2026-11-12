"""Clip rendering and export services."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.models import Clip, SourceVideo, SubtitlePreset, Transcription
from app.media.ai_upscale import apply_ai_upscale_if_requested
from app.media.reframe import plan_reframe_for_clip
from app.media.renderer import render_clip
from app.media.subtitles.ass_generator import build_ass_for_clip, write_ass_file
from app.schemas.clip_config import ClipConfiguration
from app.services.audio_studio import build_mix_plan_for_clip, ensure_original_track, get_mix_settings
from app.services.clip_config import get_clip_configuration, style_dict_from_config
from app.services.transcriptions import get_latest_transcription
from app.storage.paths import video_temp_dir

logger = get_logger(__name__)


def _load_preset(db: Session, clip: Clip, slug: str | None = None) -> dict[str, Any]:
    if clip.subtitle_preset_id:
        preset = db.get(SubtitlePreset, clip.subtitle_preset_id)
        if preset:
            return dict(preset.config_json)
    target = slug or "hormozi"
    preset = db.scalar(select(SubtitlePreset).where(SubtitlePreset.slug == target))
    if preset:
        return dict(preset.config_json)
    path = Path(__file__).resolve().parents[3] / "resources" / "subtitle-presets" / f"{target}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"slug": "hormozi", "font_family": "DejaVu Sans", "font_size": 64, "word_highlight": True}


def _words_for_clip(transcription: Transcription | None) -> list[dict[str, Any]]:
    if not transcription:
        return []
    words: list[dict[str, Any]] = []
    for seg in transcription.segments_json or []:
        for word in seg.get("words") or []:
            words.append(
                {
                    "word": word.get("word"),
                    "start": word.get("start"),
                    "end": word.get("end"),
                    "confidence": word.get("confidence"),
                }
            )
    if words:
        return words
    for word in getattr(transcription, "words", []) or []:
        words.append({"word": word.word, "start": word.start, "end": word.end, "confidence": word.confidence})
    return words


def _words_from_segments(segments: list[dict[str, Any]], *, clip_start: float) -> list[dict[str, Any]]:
    """Convert edited subtitle segments into word-like entries for ASS generation."""
    words: list[dict[str, Any]] = []
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start", 0)) + clip_start
        end = float(seg.get("end", start + 1)) + clip_start
        tokens = text.split()
        if not tokens:
            continue
        span = max(end - start, 0.05)
        step = span / len(tokens)
        for index, token in enumerate(tokens):
            words.append(
                {
                    "word": token,
                    "start": start + index * step,
                    "end": start + (index + 1) * step,
                    "confidence": 1.0,
                }
            )
    return words


def _format_filename(pattern: str, clip: Clip) -> str:
    title = re.sub(r"[^\w\-]+", "_", (clip.title or clip.hook or "clip").strip())[:40] or "clip"
    values = {
        "title": title,
        "id": clip.id,
        "id8": clip.id[:8],
        "category": (clip.category or "general"),
        "score": str(int(clip.score or 0)),
    }
    name = pattern or "{title}_{id8}"
    try:
        name = name.format(**values)
    except Exception:
        name = f"{values['title']}_{values['id8']}"
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")
    if not name.lower().endswith(".mp4"):
        name += ".mp4"
    return name


def render_clip_asset(
    db: Session,
    clip_id: str,
    *,
    reframing_mode: str | None = None,
    subtitle_preset: str | None = None,
    burn_subtitles: bool | None = None,
    output_name: str | None = None,
    configuration: ClipConfiguration | None = None,
    preview: bool = False,
) -> Clip:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ValueError(f"Clip not found: {clip_id}")
    video = db.get(SourceVideo, clip.video_id)
    if not video:
        raise ValueError(f"Source video missing for clip {clip_id}")
    source = Path(video.stored_path)
    if not source.exists():
        raise FileNotFoundError(f"Source file missing: {source}")

    cfg = configuration or get_clip_configuration(db, clip)
    if reframing_mode:
        cfg.reframe.mode = reframing_mode  # type: ignore[assignment]
    if subtitle_preset:
        cfg.subtitles.preset_slug = subtitle_preset
    if burn_subtitles is not None:
        cfg.subtitles.enabled = bool(burn_subtitles)

    # Preview uses draft/fast encoding; finals keep the configured profile.
    if preview and cfg.video.quality_preset in {"balanced", "high", "maximum"}:
        quality = "draft"
    else:
        quality = cfg.video.quality_preset

    # Optional AI upscale is never required; log availability only.
    ai_meta = apply_ai_upscale_if_requested(enabled=bool(getattr(cfg.video, "ai_upscale", False)))

    preset_file = _load_preset(db, clip, cfg.subtitles.preset_slug)
    style = style_dict_from_config(cfg)
    # Style overrides win; keep unknown keys from file preset as fallback.
    preset = {**preset_file, **style}

    transcription = get_latest_transcription(db, video.id)
    if cfg.subtitles.segments:
        words = _words_from_segments(
            [s.model_dump() for s in cfg.subtitles.segments],
            clip_start=float(clip.start_seconds),
        )
    else:
        words = _words_for_clip(transcription)

    temp_dir = video_temp_dir(video.id) / ("previews" if preview else "renders") / clip.id
    temp_dir.mkdir(parents=True, exist_ok=True)
    ass_path = temp_dir / "subtitles.ass"
    burn = bool(cfg.subtitles.enabled)
    if burn:
        ass_doc = build_ass_for_clip(
            words,
            clip_start=float(clip.start_seconds),
            clip_end=float(clip.end_seconds),
            preset=preset,
            play_res_x=cfg.video.width,
            play_res_y=cfg.video.height,
        )
        write_ass_file(ass_path, ass_doc)

    enable_faces = bool(cfg.reframe.enable_face_detection)
    if cfg.reframe.mode in {"gaming", "tutorial", "educational"}:
        enable_faces = False

    reframe = plan_reframe_for_clip(
        source,
        start_seconds=float(clip.start_seconds),
        duration_seconds=float(clip.duration_seconds),
        source_width=video.width,
        source_height=video.height,
        output_width=cfg.video.width,
        output_height=cfg.video.height,
        mode=cfg.reframe.mode,
        background_color=cfg.reframe.background_color,
        focal_x=cfg.reframe.focal_x,
        focal_y=cfg.reframe.focal_y,
        manual_crop=cfg.reframe.manual_crop.model_dump() if cfg.reframe.manual_crop else None,
        enable_face_detection=enable_faces,
    )

    preserve_fps = bool(cfg.video.preserve_source_fps) or cfg.video.fps is None
    fps = None if preserve_fps else cfg.video.fps
    if not preserve_fps and cfg.video.fps is None and video.fps:
        fps = int(round(float(video.fps)))
        preserve_fps = True

    if preview:
        output_path = temp_dir / "preview.mp4"
    else:
        settings = get_settings()
        safe_name = output_name or _format_filename(cfg.export.filename_pattern, clip)
        export_root = Path(cfg.export.output_directory) if cfg.export.output_directory else (settings.exports_dir / clip.project_id)
        export_root.mkdir(parents=True, exist_ok=True)
        output_path = export_root / safe_name

    ensure_original_track(db, clip)
    mix_plan = build_mix_plan_for_clip(db, clip)
    mix_settings = get_mix_settings(clip)

    result = render_clip(
        source_path=source,
        output_path=output_path,
        start_seconds=float(clip.start_seconds),
        duration_seconds=float(clip.duration_seconds),
        reframe=reframe,
        ass_path=ass_path if burn else None,
        burn_subtitles=burn,
        mix_plan=mix_plan,
        fps=fps,
        preserve_source_fps=preserve_fps,
        codec=cfg.video.codec,
        encoder=cfg.video.encoder,
        quality_preset=quality,
        crf=cfg.video.crf,
        audio_bitrate_kbps=cfg.audio.bitrate_kbps,
    )

    clip.ass_path = str(ass_path) if burn else None
    clip.reframing_mode = reframe.mode
    clip.render_settings = {
        **cfg.model_dump(),
        "encoder": result.encoder,
        "crf_or_cq": result.crf_or_cq,
        "reframe_notes": reframe.notes,
        "effective_crop_width": reframe.effective_crop_width,
        "effective_crop_height": reframe.effective_crop_height,
        "linear_upscale": reframe.linear_upscale,
        "ai_upscale": ai_meta,
        "audio_mix": True,
        "loudnorm": mix_settings.enable_loudnorm,
        "limiter": mix_settings.enable_limiter,
        "audio_preset": mix_settings.preset_slug,
        "preview": preview,
        "preserve_source_fps": preserve_fps,
    }
    if preview:
        clip.preview_path = str(result.output_path)
        clip.status = "preview_ready"
    else:
        clip.output_path = str(result.output_path)
        clip.preview_path = str(result.output_path)
        clip.status = "rendered"
    db.commit()
    db.refresh(clip)
    logger.info("%s clip %s → %s", "Previewed" if preview else "Rendered", clip.id, result.output_path)
    return clip


def export_clips(
    db: Session,
    clip_ids: list[str],
    *,
    destination_dir: Path | None = None,
) -> list[Path]:
    settings = get_settings()
    exported: list[Path] = []
    for clip_id in clip_ids:
        clip = db.get(Clip, clip_id)
        if not clip:
            continue
        if not clip.output_path or not Path(clip.output_path).exists():
            clip = render_clip_asset(db, clip_id)
        source = Path(clip.output_path)
        target_dir = destination_dir or (settings.exports_dir / clip.project_id / "batch")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        exported.append(target)
        clip.status = "exported"
        db.commit()
    return exported
