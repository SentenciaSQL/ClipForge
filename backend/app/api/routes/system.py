"""System maintenance: GPU, cache, recovery status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.gpu_manager import gpu_manager
from app.services import cache_service
from app.services.recovery import recover_interrupted_jobs

router = APIRouter()


class ClearCacheRequest(BaseModel):
    kind: str = Field(default="all", pattern="^(transcription|renders|audio_extract|all)$")
    video_id: str | None = None
    older_than_hours: float | None = Field(default=None, ge=0)


@router.get("/system/gpu")
def gpu_status() -> dict:
    return gpu_manager.status().to_dict()


@router.post("/system/gpu/unload-whisper")
def unload_whisper() -> dict:
    return gpu_manager.unload_whisper(reason="api")


@router.get("/system/cache")
def cache_inventory(
    kind: str = Query(default="all", pattern="^(transcription|renders|audio_extract|all)$"),
) -> dict:
    return cache_service.inventory(kind=kind)  # type: ignore[arg-type]


@router.post("/system/cache/clear")
def clear_cache(payload: ClearCacheRequest) -> dict:
    return cache_service.clear_cache(
        kind=payload.kind,  # type: ignore[arg-type]
        video_id=payload.video_id,
        older_than_hours=payload.older_than_hours,
    )


@router.post("/system/recovery/scan", response_model=dict)
def scan_recovery(db: Session = Depends(get_db)) -> dict:
    """Re-run interrupted-job reconciliation (also runs automatically on startup)."""
    return recover_interrupted_jobs(db)


@router.get("/system/status")
def system_status(db: Session = Depends(get_db)) -> dict:
    cache = cache_service.inventory()
    gpu = gpu_manager.status().to_dict()
    return {
        "gpu": gpu,
        "cache": {
            "total_bytes": cache["total_bytes"],
            "entry_count": cache["entry_count"],
            "by_kind": cache["by_kind"],
        },
        "message": "ok",
    }
