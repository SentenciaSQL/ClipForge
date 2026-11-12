"""Clip render, patch, and export endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.database.models import Clip, ProcessingJob, SubtitlePreset
from app.media.http_media import file_response_for_media
from app.orchestrator.job_manager import job_manager
from app.schemas.common import MessageResponse
from app.schemas.highlights import ClipOut
from app.schemas.jobs import ProcessingJobOut
from app.schemas.rendering import ExportClipsRequest, PatchClipRequest, RenderClipRequest
from app.services.highlights import clip_to_out

router = APIRouter()


def _queue_render_job(db: Session, clip: Clip, payload: RenderClipRequest) -> ProcessingJob:
    settings = payload.model_dump()
    job = ProcessingJob(
        project_id=clip.project_id,
        video_id=clip.video_id,
        clip_id=clip.id,
        job_type="render",
        status="queued",
        current_stage="queued",
        progress=0.0,
        message="Queued preview render" if payload.preview else "Queued for FFmpeg render",
        stages_json=[
            {"stage": "subtitle_generation", "status": "pending"},
            {"stage": "visual_analysis", "status": "pending"},
            {"stage": "rendering", "status": "pending"},
            {"stage": "export", "status": "pending"},
        ],
        result_json={"settings": settings},
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_manager.submit_render(job.id)
    return job


@router.get("/clips/{clip_id}", response_model=ClipOut)
def get_clip(clip_id: str, db: Session = Depends(get_db)) -> ClipOut:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip_to_out(clip)


@router.patch("/clips/{clip_id}", response_model=ClipOut)
def patch_clip(clip_id: str, payload: PatchClipRequest, db: Session = Depends(get_db)) -> ClipOut:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    data = payload.model_dump(exclude_unset=True)
    if "start_seconds" in data or "end_seconds" in data:
        start = float(data.get("start_seconds", clip.start_seconds))
        end = float(data.get("end_seconds", clip.end_seconds))
        if end <= start:
            raise HTTPException(status_code=400, detail="end_seconds must be greater than start_seconds")
        duration = end - start
        # Keep edits in a short-form range (matches generation max of 180s).
        if duration < 1 or duration > 180:
            raise HTTPException(status_code=400, detail="Clip duration must stay between 1 and 180 seconds")
        clip.start_seconds = start
        clip.end_seconds = end
        clip.duration_seconds = duration
        data.pop("start_seconds", None)
        data.pop("end_seconds", None)
    if "subtitle_preset_id" in data and data["subtitle_preset_id"]:
        preset = db.get(SubtitlePreset, data["subtitle_preset_id"])
        if not preset:
            raise HTTPException(status_code=400, detail="Subtitle preset not found")
    for key, value in data.items():
        setattr(clip, key, value)
    # Edits invalidate previous render.
    if any(k in payload.model_dump(exclude_unset=True) for k in ("start_seconds", "end_seconds", "reframing_mode", "subtitle_preset_id")):
        clip.status = "candidate"
        clip.output_path = None
    db.commit()
    db.refresh(clip)
    return clip_to_out(clip)


@router.post(
    "/clips/{clip_id}/render",
    response_model=ProcessingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def render_clip_endpoint(
    clip_id: str,
    payload: RenderClipRequest | None = None,
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    job = _queue_render_job(db, clip, payload or RenderClipRequest())
    return ProcessingJobOut.model_validate(job)


@router.post(
    "/clips/export",
    response_model=ProcessingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def export_clips_endpoint(payload: ExportClipsRequest, db: Session = Depends(get_db)) -> ProcessingJobOut:
    clips = [db.get(Clip, clip_id) for clip_id in payload.clip_ids]
    if any(clip is None for clip in clips):
        raise HTTPException(status_code=404, detail="One or more clips were not found")
    project_id = clips[0].project_id if clips and clips[0] else None
    job = ProcessingJob(
        project_id=project_id,
        job_type="batch_export",
        status="queued",
        current_stage="queued",
        progress=0.0,
        message=f"Queued batch export for {len(payload.clip_ids)} clips",
        stages_json=[{"stage": "export", "status": "pending"}],
        result_json={"settings": payload.model_dump()},
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_manager.submit_batch_export(job.id)
    return ProcessingJobOut.model_validate(job)


@router.get("/clips/{clip_id}/media")
def stream_clip_media(
    clip_id: str,
    kind: str = Query(default="auto", pattern="^(auto|preview|output)$"),
    db: Session = Depends(get_db),
) -> FileResponse:
    """
    Stream a rendered clip preview/output for in-browser playback.

    kind=auto prefers preview_path, then output_path.
    """
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    candidates: list[Path] = []
    if kind in {"auto", "preview"} and clip.preview_path:
        candidates.append(Path(clip.preview_path))
    if kind in {"auto", "output"} and clip.output_path:
        candidates.append(Path(clip.output_path))
    # Deduplicate while preserving order.
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            return file_response_for_media(path)

    raise HTTPException(
        status_code=404,
        detail="No playable preview/output yet. Run Preview render or Export MP4 first.",
    )


@router.post("/clips/{clip_id}/open-folder", response_model=MessageResponse)
def open_output_folder(clip_id: str, db: Session = Depends(get_db)) -> MessageResponse:
    """Return the export folder path for the desktop shell to open."""
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    settings = get_settings()
    folder = Path(clip.output_path).parent if clip.output_path else (settings.exports_dir / clip.project_id)
    folder.mkdir(parents=True, exist_ok=True)
    return MessageResponse(message=str(folder))


@router.delete("/clips/{clip_id}", response_model=MessageResponse)
def delete_clip(clip_id: str, db: Session = Depends(get_db)) -> MessageResponse:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    output = Path(clip.output_path) if clip.output_path else None
    db.delete(clip)
    db.commit()
    if output and output.exists():
        try:
            output.unlink()
        except OSError:
            pass
    return MessageResponse(message="Clip deleted")
