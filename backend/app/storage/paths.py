"""Workspace path helpers for imported media and exports."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from app.core.config import Settings, get_settings

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
    ".wmv",
    ".flv",
    ".mpeg",
    ".mpg",
    ".ts",
}


def sanitize_filename(name: str) -> str:
    base = Path(name).name
    cleaned = SAFE_NAME_RE.sub("_", base).strip("._")
    return cleaned or f"video_{uuid.uuid4().hex[:8]}"


def is_supported_video(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def project_media_dir(project_id: str, settings: Settings | None = None) -> Path:
    cfg = settings or get_settings()
    path = cfg.originals_dir / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_uploaded_video(
    project_id: str,
    source_path: Path,
    original_filename: str,
    settings: Settings | None = None,
) -> Path:
    cfg = settings or get_settings()
    destination_dir = project_media_dir(project_id, cfg)
    safe_name = sanitize_filename(original_filename)
    unique_name = f"{uuid.uuid4().hex[:10]}_{safe_name}"
    destination = destination_dir / unique_name
    shutil.copy2(source_path, destination)
    return destination


def video_temp_dir(video_id: str, settings: Settings | None = None) -> Path:
    cfg = settings or get_settings()
    path = cfg.temporary_dir / video_id
    path.mkdir(parents=True, exist_ok=True)
    return path
