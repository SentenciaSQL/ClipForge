"""Settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.settings import AppSettingsOut, AppSettingsUpdate
from app.services.settings_service import get_app_settings, update_app_settings

router = APIRouter()


@router.get("/settings", response_model=AppSettingsOut)
def read_settings(db: Session = Depends(get_db)) -> AppSettingsOut:
    return get_app_settings(db)


@router.patch("/settings", response_model=AppSettingsOut)
def patch_settings(payload: AppSettingsUpdate, db: Session = Depends(get_db)) -> AppSettingsOut:
    return update_app_settings(db, payload)
