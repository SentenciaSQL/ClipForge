"""Create / reuse a whole-video clip for audio + subtitle dubbing (no highlight clipping)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Clip, SourceVideo, SubtitlePreset
from app.services.clip_config import get_clip_configuration, save_clip_configuration

FULL_VIDEO_CATEGORY = "full_video"
# Safety ceiling for accidental runaway durations (≈3h).
FULL_VIDEO_MAX_SECONDS = 3 * 60 * 60.0
SHORT_FORM_MAX_SECONDS = 180.0


def is_full_video_clip(clip: Clip | None) -> bool:
    if not clip:
        return False
    if (clip.category or "") == FULL_VIDEO_CATEGORY:
        return True
    settings = clip.render_settings if isinstance(clip.render_settings, dict) else {}
    return bool(settings.get("full_video"))


def max_render_seconds_for_clip(clip: Clip, video: SourceVideo | None = None) -> float:
    if is_full_video_clip(clip):
        if video and video.duration_seconds and float(video.duration_seconds) > 0:
            return min(FULL_VIDEO_MAX_SECONDS, float(video.duration_seconds) + 1.0)
        return FULL_VIDEO_MAX_SECONDS
    return SHORT_FORM_MAX_SECONDS


def find_full_video_clip(db: Session, video_id: str) -> Clip | None:
    return db.scalar(
        select(Clip)
        .where(Clip.video_id == video_id, Clip.category == FULL_VIDEO_CATEGORY)
        .order_by(Clip.created_at.desc())
    )


def upsert_full_video_clip(
    db: Session,
    video: SourceVideo,
    *,
    subtitle_preset_slug: str = "hormozi",
    title: str | None = None,
) -> Clip:
    """Ensure one full-span clip exists for replace-audio / burn-subtitles workflows."""
    duration = float(video.duration_seconds or 0.0)
    if duration < 0.5:
        raise ValueError("Video duration is unknown or too short for a full-video job")
    if duration > FULL_VIDEO_MAX_SECONDS:
        duration = FULL_VIDEO_MAX_SECONDS

    preset = db.scalar(select(SubtitlePreset).where(SubtitlePreset.slug == subtitle_preset_slug))
    clip = find_full_video_clip(db, video.id)
    display_title = (title or video.original_filename or "Full video").strip()[:120]

    if clip is None:
        clip = Clip(
            project_id=video.project_id,
            video_id=video.id,
            highlight_id=None,
            title=display_title,
            start_seconds=0.0,
            end_seconds=duration,
            duration_seconds=duration,
            score=1.0,
            category=FULL_VIDEO_CATEGORY,
            hook="Full video — audio & subtitles",
            transcript=None,
            subtitle_preset_id=preset.id if preset else None,
            reframing_mode="original",
            status="candidate",
            render_settings={"full_video": True, "rank": 0},
            audio_config={"generation_audio_mode": "replace"},
        )
        db.add(clip)
    else:
        clip.title = display_title
        clip.start_seconds = 0.0
        clip.end_seconds = duration
        clip.duration_seconds = duration
        clip.category = FULL_VIDEO_CATEGORY
        clip.hook = clip.hook or "Full video — audio & subtitles"
        clip.status = "candidate" if not clip.output_path else clip.status
        settings = dict(clip.render_settings or {})
        settings["full_video"] = True
        clip.render_settings = settings
        if preset and not clip.subtitle_preset_id:
            clip.subtitle_preset_id = preset.id

    db.commit()
    db.refresh(clip)

    # Seed default clip configuration with original frame (no vertical crop) for dubbing.
    cfg = get_clip_configuration(db, clip)
    cfg.reframe.mode = "original"  # type: ignore[assignment]
    cfg.subtitles.enabled = True
    if subtitle_preset_slug:
        cfg.subtitles.preset_slug = subtitle_preset_slug
    save_clip_configuration(db, clip, cfg)
    db.refresh(clip)
    return clip
