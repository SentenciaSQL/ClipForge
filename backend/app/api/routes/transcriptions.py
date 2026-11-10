"""Transcription endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import ProcessingJob
from app.orchestrator.job_manager import job_manager
from app.schemas.jobs import ProcessingJobOut
from app.schemas.transcriptions import TranscribeRequest, TranscriptionOut
from app.services.projects import get_project
from app.services.transcriptions import get_latest_transcription, get_transcription, transcription_to_out
from app.services.videos import get_video

router = APIRouter()


def _queue_transcription_job(
    db: Session,
    *,
    video_id: str,
    language: str | None,
    whisper_model: str | None,
    force: bool,
) -> ProcessingJob:
    video = get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not get_project(db, video.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    job = ProcessingJob(
        project_id=video.project_id,
        video_id=video.id,
        job_type="analyze",
        status="queued",
        current_stage="queued",
        progress=0.0,
        message="Queued for audio extraction and transcription",
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
                "language": language,
                "whisper_model": whisper_model,
                "force": force,
            }
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_manager.submit_analyze(job.id)
    return job


@router.post(
    "/videos/{video_id}/transcribe",
    response_model=ProcessingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def transcribe_video(
    video_id: str,
    payload: TranscribeRequest,
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    job = _queue_transcription_job(
        db,
        video_id=video_id,
        language=payload.language,
        whisper_model=payload.whisper_model,
        force=payload.force,
    )
    return ProcessingJobOut.model_validate(job)


@router.get("/videos/{video_id}/transcription", response_model=TranscriptionOut)
def get_video_transcription(
    video_id: str,
    include_details: bool = True,
    db: Session = Depends(get_db),
) -> TranscriptionOut:
    if not get_video(db, video_id):
        raise HTTPException(status_code=404, detail="Video not found")
    transcription = get_latest_transcription(db, video_id)
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")
    # Ensure words relationship is available when include_details.
    detailed = get_transcription(db, transcription.id) or transcription
    return transcription_to_out(detailed, include_details=include_details)


@router.get("/transcriptions/{transcription_id}", response_model=TranscriptionOut)
def get_transcription_by_id(
    transcription_id: str,
    include_details: bool = True,
    db: Session = Depends(get_db),
) -> TranscriptionOut:
    transcription = get_transcription(db, transcription_id)
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return transcription_to_out(transcription, include_details=include_details)
