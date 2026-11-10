"""Settings read/update backed by env defaults + optional SQLite overrides."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.hardware import detect_hardware, refresh_hardware_profile
from app.database.models import AppSettings
from app.schemas.settings import AppSettingsOut, AppSettingsUpdate

SETTINGS_KEY = "runtime"


def _load_overrides(db: Session) -> dict[str, Any]:
    row = db.scalar(select(AppSettings).where(AppSettings.key == SETTINGS_KEY))
    return dict(row.value_json) if row else {}


def get_app_settings(db: Session) -> AppSettingsOut:
    settings = get_settings()
    overrides = _load_overrides(db)
    hardware = detect_hardware().to_dict()

    return AppSettingsOut(
        ollama_url=overrides.get("ollama_url", settings.ollama_url),
        ollama_model=overrides.get("ollama_model", settings.ollama_model),
        whisper_model=overrides.get("whisper_model", settings.whisper_model),
        whisper_device=overrides.get("whisper_device", settings.whisper_device),
        prefer_gpu=overrides.get("prefer_gpu", settings.prefer_gpu),
        max_concurrent_jobs=overrides.get("max_concurrent_jobs", settings.max_concurrent_jobs),
        use_nvenc=overrides.get("use_nvenc", settings.use_nvenc),
        ffmpeg_path=overrides.get("ffmpeg_path") or hardware.get("ffmpeg_path"),
        ffprobe_path=overrides.get("ffprobe_path") or hardware.get("ffprobe_path"),
        workspace_path=str(overrides.get("workspace_path", settings.workspace_path)),
        output_width=overrides.get("output_width", settings.output_width),
        output_height=overrides.get("output_height", settings.output_height),
        output_fps=overrides.get("output_fps", settings.output_fps),
        crf=overrides.get("crf", settings.crf),
        clip_min_seconds=overrides.get("clip_min_seconds", settings.clip_min_seconds),
        clip_max_seconds=overrides.get("clip_max_seconds", settings.clip_max_seconds),
        hardware=hardware,
    )


def update_app_settings(db: Session, payload: AppSettingsUpdate) -> AppSettingsOut:
    overrides = _load_overrides(db)
    updates = payload.model_dump(exclude_unset=True)
    overrides.update(updates)

    row = db.scalar(select(AppSettings).where(AppSettings.key == SETTINGS_KEY))
    if row:
        row.value_json = overrides
    else:
        db.add(AppSettings(key=SETTINGS_KEY, value_json=overrides))
    db.commit()

    # Paths may have changed — refresh hardware cache next read.
    refresh_hardware_profile()
    get_settings.cache_clear()
    return get_app_settings(db)
