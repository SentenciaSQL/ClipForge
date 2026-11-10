"""Clip rendering and export services."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.models import Clip, SourceVideo, SubtitlePreset, Transcription
from app.media.reframe import plan_reframe_for_clip
from app.media.renderer import render_clip
from app.media.subtitles.ass_generator import build_ass_for_clip, write_ass_file
from app.services.audio_studio import build_mix_plan_for_clip, ensure_original_track, get_mix_settings
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
    # Fallback to file on disk
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
    # Fallback from relationship if loaded
    for word in getattr(transcription, "words", []) or []:
        words.append({"word": word.word, "start": word.start, "end": word.end, "confidence": word.confidence})
    return words


def render_clip_asset(
    db: Session,
    clip_id: str,
    *,
    reframing_mode: str | None = None,
    subtitle_preset: str | None = None,
    burn_subtitles: bool = True,
    output_name: str | None = None,
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

    settings = get_settings()
    mode = reframing_mode or clip.reframing_mode or "auto"
    preset = _load_preset(db, clip, subtitle_preset)
    transcription = get_latest_transcription(db, video.id)
    words = _words_for_clip(transcription)

    temp_dir = video_temp_dir(video.id) / "renders" / clip.id
    temp_dir.mkdir(parents=True, exist_ok=True)
    ass_path = temp_dir / "subtitles.ass"
    ass_doc = build_ass_for_clip(
        words,
        clip_start=float(clip.start_seconds),
        clip_end=float(clip.end_seconds),
        preset=preset,
        play_res_x=settings.output_width,
        play_res_y=settings.output_height,
    )
    write_ass_file(ass_path, ass_doc)

    reframe = plan_reframe_for_clip(
        source,
        start_seconds=float(clip.start_seconds),
        duration_seconds=float(clip.duration_seconds),
        source_width=video.width,
        source_height=video.height,
        output_width=settings.output_width,
        output_height=settings.output_height,
        mode=mode,
    )

    safe_name = output_name or f"{clip.id[:8]}_{(clip.title or 'clip').replace(' ', '_')[:40]}.mp4"
    for ch in '<>:"/\\|?*':
        safe_name = safe_name.replace(ch, "_")
    if not safe_name.lower().endswith(".mp4"):
        safe_name += ".mp4"
    export_dir = settings.exports_dir / clip.project_id
    export_dir.mkdir(parents=True, exist_ok=True)
    output_path = export_dir / safe_name

    ensure_original_track(db, clip)
    mix_plan = build_mix_plan_for_clip(db, clip)
    mix_settings = get_mix_settings(clip)

    result = render_clip(
        source_path=source,
        output_path=output_path,
        start_seconds=float(clip.start_seconds),
        duration_seconds=float(clip.duration_seconds),
        reframe=reframe,
        ass_path=ass_path if burn_subtitles else None,
        burn_subtitles=burn_subtitles,
        mix_plan=mix_plan,
    )

    clip.output_path = str(result.output_path)
    clip.ass_path = str(ass_path)
    clip.preview_path = str(result.output_path)
    clip.reframing_mode = reframe.mode
    clip.status = "rendered"
    clip.render_settings = {
        **(clip.render_settings or {}),
        "encoder": result.encoder,
        "reframe": reframe.mode,
        "reframe_notes": reframe.notes,
        "burn_subtitles": burn_subtitles,
        "subtitle_preset": preset.get("slug") or preset.get("name"),
        "output_width": settings.output_width,
        "output_height": settings.output_height,
        "audio_mix": True,
        "loudnorm": mix_settings.enable_loudnorm,
        "limiter": mix_settings.enable_limiter,
        "audio_preset": mix_settings.preset_slug,
    }
    db.commit()
    db.refresh(clip)
    logger.info("Rendered clip %s → %s", clip.id, clip.output_path)
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
