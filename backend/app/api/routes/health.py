"""Health and hardware endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.core.hardware import detect_hardware, refresh_hardware_profile
from app.schemas.settings import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version=__version__, hardware=detect_hardware().to_dict())


@router.get("/hardware")
def hardware(refresh: bool = False) -> dict:
    profile = refresh_hardware_profile() if refresh else detect_hardware()
    return profile.to_dict()
