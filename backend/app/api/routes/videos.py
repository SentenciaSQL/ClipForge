"""Video import and metadata endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import ProcessingJob
from app.orchestrator.job_manager import job_manager
from app.schemas.common import MessageResponse
from app.schemas.jobs import ProcessingJobOut
from app.schemas.videos import AnalyzeRequest, SourceVideoOut, VideoImportResponse, VideoMetadataOut
from app.services.projects import get_project
from app.services.videos import (
    delete_video,
    get_video,
    import_video_file,
    list_videos,
    refresh_video_metadata,
    video_to_out,
)

router = APIRouter()


@router.post(
    "/videos/import",
    response_model=VideoImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_video(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    project_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> VideoImportResponse:
    try:
        project, video = await import_video_file(
            db,
            project_id=project_id,
            project_name=project_name,
            upload=file,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc

    return VideoImportResponse(
        project={
            "id": project.id,
            "name": project.name,
            "status": project.status,
        },
        video=video_to_out(video, include_raw=False),
    )


@router.get("/videos", response_model=list[SourceVideoOut])
def get_videos(project_id: str | None = None, db: Session = Depends(get_db)) -> list[SourceVideoOut]:
    return [video_to_out(video) for video in list_videos(db, project_id)]


@router.get("/videos/{video_id}", response_model=SourceVideoOut)
def get_video_detail(video_id: str, db: Session = Depends(get_db)) -> SourceVideoOut:
    video = get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video_to_out(video, include_raw=False)


@router.get("/videos/{video_id}/metadata", response_model=VideoMetadataOut)
def get_video_metadata(video_id: str, db: Session = Depends(get_db)) -> VideoMetadataOut:
    video = get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    out = video_to_out(video, include_raw=True)
    assert out.metadata is not None
    return out.metadata


@router.post("/videos/{video_id}/metadata/refresh", response_model=SourceVideoOut)
def refresh_metadata(video_id: str, db: Session = Depends(get_db)) -> SourceVideoOut:
    try:
        video = refresh_video_metadata(db, video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video_to_out(video, include_raw=False)


@router.delete("/videos/{video_id}", response_model=MessageResponse)
def remove_video(video_id: str, db: Session = Depends(get_db)) -> MessageResponse:
    if not delete_video(db, video_id):
        raise HTTPException(status_code=404, detail="Video not found")
    return MessageResponse(message="Video deleted")


@router.post("/videos/{video_id}/analyze", response_model=ProcessingJobOut)
def analyze_video(
    video_id: str,
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    """
    Queue analysis. Phase 2 runs audio extraction + Faster-Whisper transcription.
    Later stages are marked deferred until Phase 3+.
    """
    video = get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not get_project(db, video.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    settings = payload.model_dump()
    job = ProcessingJob(
        project_id=video.project_id,
        video_id=video.id,
        job_type="analyze",
        status="queued",
        current_stage="queued",
        progress=0.0,
        message="Queued for audio extraction and local transcription",
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
        result_json={"settings": settings},
        started_at=None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_manager.submit_analyze(job.id)
    return ProcessingJobOut.model_validate(job)
