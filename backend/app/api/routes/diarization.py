"""Speaker diarization endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.ai.diarization.service import pyannote_available
from app.core.config import get_settings
from app.database.models import ProcessingJob, SourceVideo
from app.orchestrator.job_manager import job_manager
from app.schemas.diarization import DiarizeRequest, SpeakerOut, SpeakerRenameRequest
from app.schemas.jobs import ProcessingJobOut
from app.services.diarization import list_speakers, rename_speaker

router = APIRouter()


@router.get("/diarization/status")
def diarization_status() -> dict:
    settings = get_settings()
    return {
        "engine_default": settings.diarization_engine,
        "max_speakers_default": settings.diarization_max_speakers,
        "pyannote_available": pyannote_available(),
        "hf_token_configured": bool(settings.hf_token),
        "local_available": True,
        "cost": "local_only",
        "notes": [
            "local engine needs no token and runs fully offline",
            "pyannote needs a free Hugging Face token to download model weights once",
        ],
    }


@router.get("/videos/{video_id}/speakers", response_model=list[SpeakerOut])
def get_speakers(video_id: str, db: Session = Depends(get_db)) -> list[SpeakerOut]:
    video = db.get(SourceVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return [SpeakerOut.model_validate(row) for row in list_speakers(db, video_id)]


@router.patch("/speakers/{speaker_id}", response_model=SpeakerOut)
def patch_speaker(
    speaker_id: str,
    payload: SpeakerRenameRequest,
    db: Session = Depends(get_db),
) -> SpeakerOut:
    try:
        speaker = rename_speaker(db, speaker_id, payload.display_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SpeakerOut.model_validate(speaker)


@router.post(
    "/videos/{video_id}/diarize",
    response_model=ProcessingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def diarize_video(
    video_id: str,
    payload: DiarizeRequest | None = None,
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    video = db.get(SourceVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    body = payload or DiarizeRequest()
    job = ProcessingJob(
        project_id=video.project_id,
        video_id=video.id,
        job_type="diarize",
        status="queued",
        current_stage="queued",
        progress=0.0,
        message="Queued speaker diarization",
        stages_json=[{"stage": "diarization", "status": "pending"}],
        result_json={"settings": body.model_dump()},
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_manager.submit_diarize(job.id)
    return ProcessingJobOut.model_validate(job)
