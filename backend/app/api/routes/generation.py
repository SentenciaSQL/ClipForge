"""Generation configuration and profile endpoints for the import wizard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.generation_config import (
    GenerationConfiguration,
    GenerationConfigurationOut,
    GenerationConfigurationPatch,
    GenerationProfileDuplicate,
    GenerationProfileIn,
    GenerationProfileOut,
    GenerationProfileUpdate,
)
from app.services import generation_config as gen_service
from app.services.videos import ensure_video_thumbnail, get_video

router = APIRouter()


@router.get("/videos/{video_id}/generation-configuration", response_model=GenerationConfigurationOut)
def get_generation_configuration(video_id: str, db: Session = Depends(get_db)) -> GenerationConfigurationOut:
    video = get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return gen_service.configuration_out(db, video)


@router.put("/videos/{video_id}/generation-configuration", response_model=GenerationConfigurationOut)
def put_generation_configuration(
    video_id: str,
    payload: GenerationConfigurationPatch,
    db: Session = Depends(get_db),
) -> GenerationConfigurationOut:
    video = get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    config = payload.configuration
    if payload.apply_profile and payload.profile_id:
        if not payload.confirm_overwrite:
            # Still allow if current config is empty/default.
            current = gen_service.get_generation_configuration(video)
            if video.generation_config_json and current.model_dump() != gen_service.default_generation_configuration().model_dump():
                raise HTTPException(
                    status_code=400,
                    detail="confirm_overwrite required to replace existing generation settings with a profile",
                )
        try:
            profile = gen_service.get_generation_profile(db, payload.profile_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        config = GenerationConfiguration.model_validate(profile.config_json)
        config.profile_id = profile.id
        config.profile_slug = profile.slug

    validation = gen_service.validate_generation_configuration(config, video=video)
    if not validation.get("ok"):
        raise HTTPException(status_code=400, detail={"validation": validation})

    gen_service.save_generation_configuration(db, video, config)
    return gen_service.configuration_out(db, video)


@router.post("/videos/{video_id}/generation-configuration/validate", response_model=dict)
def validate_generation_configuration(
    video_id: str,
    payload: GenerationConfiguration,
    db: Session = Depends(get_db),
) -> dict:
    video = get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    validation = gen_service.validate_generation_configuration(payload, video=video)
    return {
        "validation": validation,
        "summary": gen_service.build_summary(payload),
    }


@router.get("/videos/{video_id}/thumbnail")
def get_video_thumbnail(video_id: str, db: Session = Depends(get_db)):
    video = get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    path = ensure_video_thumbnail(video)
    if path:
        db.commit()
    if not path:
        raise HTTPException(status_code=404, detail="Thumbnail unavailable")
    return FileResponse(path, media_type="image/jpeg", filename="poster.jpg")


@router.get("/generation-profiles", response_model=list[GenerationProfileOut])
def list_generation_profiles(db: Session = Depends(get_db)) -> list[GenerationProfileOut]:
    return gen_service.list_generation_profiles(db)


@router.post(
    "/generation-profiles",
    response_model=GenerationProfileOut,
    status_code=status.HTTP_201_CREATED,
)
def create_generation_profile(
    payload: GenerationProfileIn,
    db: Session = Depends(get_db),
) -> GenerationProfileOut:
    try:
        return gen_service.create_generation_profile(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/generation-profiles/{profile_id}", response_model=GenerationProfileOut)
def update_generation_profile(
    profile_id: str,
    payload: GenerationProfileUpdate,
    db: Session = Depends(get_db),
) -> GenerationProfileOut:
    try:
        return gen_service.update_generation_profile(
            db,
            profile_id,
            name=payload.name,
            description=payload.description,
            config_json=payload.config_json,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/generation-profiles/{profile_id}/duplicate",
    response_model=GenerationProfileOut,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_generation_profile(
    profile_id: str,
    payload: GenerationProfileDuplicate | None = None,
    db: Session = Depends(get_db),
) -> GenerationProfileOut:
    try:
        return gen_service.duplicate_generation_profile(
            db,
            profile_id,
            name=(payload.name if payload else None),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/generation-profiles/{profile_id}")
def delete_generation_profile(profile_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        gen_service.delete_generation_profile(db, profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Generation profile deleted"}
