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
    Queue analysis. Requires an explicit Generate Clips action from the UI.
    Accepts a full generation_config (preferred) or legacy flat analyze fields.
    """
    video = get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not get_project(db, video.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    from app.schemas.generation_config import GenerationConfiguration
    from app.services.generation_config import (
        get_generation_configuration,
        save_generation_configuration,
        validate_generation_configuration,
    )

    if payload.generation_config:
        try:
            gen_cfg = GenerationConfiguration.model_validate(payload.generation_config)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Invalid generation_config: {exc}") from exc
    else:
        # Merge legacy flat fields onto saved/default generation config.
        gen_cfg = get_generation_configuration(video)
        data = gen_cfg.model_dump()
        data["analysis"]["language"] = payload.language
        if payload.whisper_model:
            data["analysis"]["whisper_model"] = payload.whisper_model
        if payload.ollama_model:
            data["analysis"]["ollama_model"] = payload.ollama_model
        data["analysis"]["force_retranscribe"] = payload.force
        data["duration"]["clip_count"] = payload.clip_count
        data["duration"]["min_duration"] = payload.min_duration
        data["duration"]["max_duration"] = payload.max_duration
        data["subtitles"]["preset_slug"] = payload.subtitle_preset
        if payload.burn_subtitles is not None:
            data["subtitles"]["enabled"] = payload.burn_subtitles
        data["reframe"]["mode"] = payload.reframing_mode
        gen_cfg = GenerationConfiguration.model_validate(data)

    validation = validate_generation_configuration(gen_cfg, video=video)
    if not validation.get("ok"):
        raise HTTPException(status_code=400, detail={"validation": validation})

    if payload.save_configuration:
        save_generation_configuration(db, video, gen_cfg)

    settings = gen_cfg.to_analyze_settings(video_duration=video.duration_seconds)
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
