"""Highlight and clip listing / regenerate endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import ProcessingJob
from app.orchestrator.job_manager import job_manager
from app.schemas.highlights import ClipOut, HighlightOut, HighlightsRequest
from app.schemas.jobs import ProcessingJobOut
from app.services.highlights import (
    clip_to_out,
    highlight_to_out,
    list_clips_for_project,
    list_clips_for_video,
    list_highlights,
)
from app.services.projects import get_project
from app.services.transcriptions import get_latest_transcription
from app.services.videos import get_video

router = APIRouter()


@router.get("/videos/{video_id}/highlights", response_model=list[HighlightOut])
def get_video_highlights(
    video_id: str,
    selected_only: bool = False,
    db: Session = Depends(get_db),
) -> list[HighlightOut]:
    if not get_video(db, video_id):
        raise HTTPException(status_code=404, detail="Video not found")
    return [highlight_to_out(row) for row in list_highlights(db, video_id, selected_only=selected_only)]


@router.post(
    "/videos/{video_id}/highlights",
    response_model=ProcessingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def regenerate_highlights(
    video_id: str,
    payload: HighlightsRequest,
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    video = get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not get_latest_transcription(db, video_id):
        raise HTTPException(
            status_code=400,
            detail="Transcription required before highlight detection. Run analyze/transcribe first.",
        )

    job = ProcessingJob(
        project_id=video.project_id,
        video_id=video.id,
        job_type="analyze",
        status="queued",
        current_stage="queued",
        progress=0.0,
        message="Queued for semantic highlight detection",
        stages_json=[
            {"stage": "import", "status": "completed"},
            {"stage": "metadata", "status": "completed"},
            {"stage": "audio_extraction", "status": "pending"},
            {"stage": "transcription", "status": "pending"},
            {"stage": "semantic_analysis", "status": "pending"},
            {"stage": "highlight_selection", "status": "pending"},
            {"stage": "visual_analysis", "status": "pending"},
            {"stage": "subtitle_generation", "status": "pending"},
            {"stage": "rendering", "status": "pending"},
            {"stage": "export", "status": "pending"},
        ],
        result_json={
            "settings": {
                "force": False,
                "clip_count": payload.clip_count,
                "min_duration": payload.min_duration,
                "max_duration": payload.max_duration,
                "ollama_model": payload.ollama_model,
                "subtitle_preset": payload.subtitle_preset,
            }
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_manager.submit_analyze(job.id)
    return ProcessingJobOut.model_validate(job)


@router.get("/videos/{video_id}/clips", response_model=list[ClipOut])
def get_video_clips(video_id: str, db: Session = Depends(get_db)) -> list[ClipOut]:
    if not get_video(db, video_id):
        raise HTTPException(status_code=404, detail="Video not found")
    return [clip_to_out(row) for row in list_clips_for_video(db, video_id)]


@router.get("/projects/{project_id}/clips", response_model=list[ClipOut])
def get_project_clips(project_id: str, db: Session = Depends(get_db)) -> list[ClipOut]:
    if not get_project(db, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return [clip_to_out(row) for row in list_clips_for_project(db, project_id)]
