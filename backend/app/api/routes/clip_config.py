"""Per-clip configuration, preview, and batch-render endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import Clip, ProcessingJob
from app.orchestrator.job_manager import job_manager
from app.schemas.clip_config import (
    ApplyConfigurationRequest,
    BatchRenderRequest,
    ClipConfiguration,
    ClipConfigurationOut,
    ClipConfigurationPatch,
    PreviewClipRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.jobs import ProcessingJobOut
from app.services.clip_config import (
    configuration_out,
    get_clip_configuration,
    merge_configuration,
    save_clip_configuration,
)
from app.services.export_profiles import get_profile

router = APIRouter()


def _queue_render(
    db: Session,
    clip: Clip,
    *,
    settings: dict,
    job_type: str = "render",
    message: str = "Queued for FFmpeg render",
) -> ProcessingJob:
    job = ProcessingJob(
        project_id=clip.project_id,
        video_id=clip.video_id,
        clip_id=clip.id,
        job_type=job_type,
        status="queued",
        current_stage="queued",
        progress=0.0,
        message=message,
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
    if job_type == "preview":
        # Reuse render worker; settings.preview flag selects preview path.
        job_manager.submit_render(job.id)
    else:
        job_manager.submit_render(job.id)
    return job


@router.get("/clips/{clip_id}/configuration", response_model=ClipConfigurationOut)
def get_configuration(clip_id: str, db: Session = Depends(get_db)) -> ClipConfigurationOut:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return configuration_out(db, clip)


@router.patch("/clips/{clip_id}/configuration", response_model=ClipConfigurationOut)
def patch_configuration(
    clip_id: str,
    payload: ClipConfigurationPatch,
    db: Session = Depends(get_db),
) -> ClipConfigurationOut:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    current = get_clip_configuration(db, clip)
    if payload.apply_profile and payload.profile_id:
        try:
            profile = get_profile(db, payload.profile_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        profile_cfg = ClipConfiguration.model_validate(profile.config_json)
        # Profile replaces nested sections, then optional patch overlays.
        merged = merge_configuration(
            profile_cfg,
            ClipConfigurationPatch(
                subtitles=payload.subtitles,
                video=payload.video,
                reframe=payload.reframe,
                audio=payload.audio,
                export=payload.export,
                profile_id=payload.profile_id,
            ),
        )
        merged.profile_id = profile.id
    else:
        merged = merge_configuration(current, payload)
        if payload.profile_id is not None:
            merged.profile_id = payload.profile_id

    save_clip_configuration(db, clip, merged)
    return configuration_out(db, clip)


@router.post("/clips/apply-configuration", response_model=MessageResponse)
def apply_configuration_many(
    payload: ApplyConfigurationRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    if not payload.confirm_overwrite:
        raise HTTPException(
            status_code=400,
            detail="confirm_overwrite must be true to apply a shared configuration to multiple clips",
        )
    updated = 0
    for clip_id in payload.clip_ids:
        clip = db.get(Clip, clip_id)
        if not clip:
            continue
        current = get_clip_configuration(db, clip)
        merged = merge_configuration(current, payload.configuration)
        save_clip_configuration(db, clip, merged)
        updated += 1
    return MessageResponse(message=f"Applied configuration to {updated} clips")


@router.post(
    "/clips/{clip_id}/preview",
    response_model=ProcessingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def preview_clip(
    clip_id: str,
    payload: PreviewClipRequest | None = None,
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    body = payload or PreviewClipRequest()
    if body.configuration and body.save_configuration:
        current = get_clip_configuration(db, clip)
        merged = merge_configuration(current, body.configuration)
        save_clip_configuration(db, clip, merged)
    settings = {
        "preview": True,
        "burn_subtitles": None,
    }
    if body.configuration:
        settings["configuration_patch"] = body.configuration.model_dump(exclude_unset=True)
    job = _queue_render(
        db,
        clip,
        settings=settings,
        job_type="render",
        message="Queued preview render",
    )
    return ProcessingJobOut.model_validate(job)


@router.post(
    "/clips/batch-render",
    response_model=ProcessingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def batch_render(payload: BatchRenderRequest, db: Session = Depends(get_db)) -> ProcessingJobOut:
    clips = [db.get(Clip, clip_id) for clip_id in payload.clip_ids]
    if any(clip is None for clip in clips):
        raise HTTPException(status_code=404, detail="One or more clips were not found")
    assert clips[0] is not None
    if payload.apply_to_all and payload.configuration:
        if not payload.confirm_overwrite:
            raise HTTPException(
                status_code=400,
                detail="confirm_overwrite required when apply_to_all is true",
            )
        for clip in clips:
            assert clip is not None
            current = get_clip_configuration(db, clip)
            merged = merge_configuration(current, payload.configuration)
            save_clip_configuration(db, clip, merged)

    job = ProcessingJob(
        project_id=clips[0].project_id,
        job_type="batch_export",
        status="queued",
        current_stage="queued",
        progress=0.0,
        message=f"Queued batch render for {len(payload.clip_ids)} clips",
        stages_json=[{"stage": "export", "status": "pending"}],
        result_json={
            "settings": {
                "clip_ids": payload.clip_ids,
                "render_if_needed": True,
                "configuration": payload.configuration.model_dump(exclude_unset=True)
                if payload.configuration
                else None,
            }
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_manager.submit_batch_export(job.id)
    return ProcessingJobOut.model_validate(job)
