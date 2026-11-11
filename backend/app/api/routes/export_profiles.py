"""Export profile CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.media.aspect import list_aspect_presets
from app.schemas.clip_config import ExportProfileIn, ExportProfileOut, ExportProfileUpdate
from app.services import export_profiles as profiles_service

router = APIRouter()


@router.get("/export-profiles", response_model=list[ExportProfileOut])
def list_export_profiles(db: Session = Depends(get_db)) -> list[ExportProfileOut]:
    return profiles_service.list_profiles(db)


@router.post(
    "/export-profiles",
    response_model=ExportProfileOut,
    status_code=status.HTTP_201_CREATED,
)
def create_export_profile(payload: ExportProfileIn, db: Session = Depends(get_db)) -> ExportProfileOut:
    try:
        return profiles_service.create_profile(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/export-profiles/{profile_id}", response_model=ExportProfileOut)
def patch_export_profile(
    profile_id: str,
    payload: ExportProfileUpdate,
    db: Session = Depends(get_db),
) -> ExportProfileOut:
    try:
        return profiles_service.update_profile(db, profile_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/export-profiles/{profile_id}")
def delete_export_profile(profile_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        profiles_service.delete_profile(db, profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Export profile deleted"}


@router.get("/export-options/aspect-ratios")
def get_aspect_ratios() -> list[dict]:
    return list_aspect_presets()
