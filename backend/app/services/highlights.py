"""Persist and query highlight candidates / clips."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.highlights.dedupe import RankedCandidate
from app.database.models import Clip, Highlight, SourceVideo, SubtitlePreset
from app.schemas.highlights import ClipOut, HighlightOut


def persist_highlights(
    db: Session,
    video: SourceVideo,
    candidates: list[RankedCandidate],
    *,
    selected: list[RankedCandidate],
    subtitle_preset_slug: str = "hormozi",
    reframing_mode: str = "auto",
    min_duration: float = 12.0,
    max_duration: float = 30.0,
) -> tuple[list[Highlight], list[Clip]]:
    from app.ai.highlights.duration_clamp import clamp_clip_window

    from sqlalchemy import or_

    from app.services.full_video_clip import FULL_VIDEO_CATEGORY

    db.execute(delete(Highlight).where(Highlight.video_id == video.id))
    # Keep full-video dub/subtitle jobs; only replace highlight-derived clips.
    # (NULL category must be deleted too — SQL != does not match NULL.)
    db.execute(
        delete(Clip).where(
            Clip.video_id == video.id,
            or_(Clip.category.is_(None), Clip.category != FULL_VIDEO_CATEGORY),
        )
    )
    db.flush()

    preset = db.scalar(select(SubtitlePreset).where(SubtitlePreset.slug == subtitle_preset_slug))
    highlight_rows: list[Highlight] = []
    selected_keys = {(round(c.start_seconds, 3), round(c.end_seconds, 3)) for c in selected}
    video_duration = float(video.duration_seconds) if video.duration_seconds else None

    for rank_index, candidate in enumerate(sorted(candidates, key=lambda c: c.score, reverse=True), start=1):
        is_selected = (round(candidate.start_seconds, 3), round(candidate.end_seconds, 3)) in selected_keys
        clamped = clamp_clip_window(
            candidate.start_seconds,
            candidate.end_seconds,
            min_seconds=float(min_duration),
            max_seconds=float(max_duration),
            video_duration=video_duration,
        )
        if clamped is None:
            continue
        start, end = clamped
        duration = round(end - start, 3)
        row = Highlight(
            video_id=video.id,
            start_seconds=start,
            end_seconds=end,
            duration_seconds=duration,
            transcript=candidate.transcript,
            hook=candidate.hook,
            category=candidate.category,
            description=candidate.description,
            score=candidate.score,
            score_breakdown=candidate.score_breakdown,
            reason=candidate.reason,
            selected=is_selected,
            rank=rank_index if is_selected else None,
        )
        db.add(row)
        highlight_rows.append(row)

    db.flush()

    clip_rows: list[Clip] = []
    selected_rows = [row for row in highlight_rows if row.selected]
    selected_rows.sort(key=lambda row: row.score, reverse=True)
    for index, row in enumerate(selected_rows, start=1):
        clip = Clip(
            project_id=video.project_id,
            video_id=video.id,
            highlight_id=row.id,
            title=row.hook[:120] if row.hook else f"Clip {index}",
            start_seconds=row.start_seconds,
            end_seconds=row.end_seconds,
            duration_seconds=row.duration_seconds,
            score=row.score,
            category=row.category,
            hook=row.hook,
            transcript=row.transcript,
            subtitle_preset_id=preset.id if preset else None,
            reframing_mode=reframing_mode or "auto",
            status="candidate",
            render_settings={"rank": index},
        )
        db.add(clip)
        clip_rows.append(clip)

    video.status = "highlights_ready"
    db.commit()
    for row in highlight_rows:
        db.refresh(row)
    for clip in clip_rows:
        db.refresh(clip)
    return highlight_rows, clip_rows


def list_highlights(db: Session, video_id: str, selected_only: bool = False) -> list[Highlight]:
    stmt = select(Highlight).where(Highlight.video_id == video_id).order_by(Highlight.score.desc())
    if selected_only:
        stmt = stmt.where(Highlight.selected.is_(True))
    return list(db.scalars(stmt).all())


def list_clips_for_project(db: Session, project_id: str) -> list[Clip]:
    return list(
        db.scalars(select(Clip).where(Clip.project_id == project_id).order_by(Clip.score.desc())).all()
    )


def list_clips_for_video(db: Session, video_id: str) -> list[Clip]:
    return list(db.scalars(select(Clip).where(Clip.video_id == video_id).order_by(Clip.score.desc())).all())


def highlight_to_out(row: Highlight) -> HighlightOut:
    return HighlightOut(
        id=row.id,
        video_id=row.video_id,
        start_seconds=row.start_seconds,
        end_seconds=row.end_seconds,
        duration_seconds=row.duration_seconds,
        transcript=row.transcript,
        hook=row.hook,
        category=row.category,
        description=row.description,
        score=row.score,
        score_breakdown=row.score_breakdown,
        reason=row.reason,
        selected=row.selected,
        rank=row.rank,
        created_at=row.created_at,
    )


def clip_to_out(row: Clip) -> ClipOut:
    return ClipOut(
        id=row.id,
        project_id=row.project_id,
        video_id=row.video_id,
        highlight_id=row.highlight_id,
        title=row.title,
        start_seconds=row.start_seconds,
        end_seconds=row.end_seconds,
        duration_seconds=row.duration_seconds,
        score=row.score,
        category=row.category,
        hook=row.hook,
        transcript=row.transcript,
        reframing_mode=row.reframing_mode,
        status=row.status,
        output_path=row.output_path,
        preview_path=row.preview_path,
        subtitle_preset_id=row.subtitle_preset_id,
        render_settings=row.render_settings,
        audio_config=row.audio_config,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
