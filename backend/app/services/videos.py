"""Video import and metadata services."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.models import Project, SourceVideo
from app.media.metadata import extract_metadata
from app.schemas.videos import SourceVideoOut, VideoMetadataOut
from app.storage.paths import is_supported_video, sanitize_filename, store_uploaded_video

logger = get_logger(__name__)


def _metadata_out(video: SourceVideo, include_raw: bool = False) -> VideoMetadataOut:
    raw = video.metadata_json if include_raw else None
    video_streams = (raw or {}).get("streams", []) if include_raw and raw else []
    # Prefer persisted columns; fall back to stored JSON summary counts.
    meta = video.metadata_json or {}
    return VideoMetadataOut(
        duration_seconds=video.duration_seconds,
        width=video.width,
        height=video.height,
        fps=video.fps,
        video_codec=video.video_codec,
        audio_codec=video.audio_codec,
        aspect_ratio=video.aspect_ratio,
        bitrate=video.bitrate,
        file_size_bytes=video.file_size_bytes,
        format_name=(meta.get("format") or {}).get("format_name") if isinstance(meta, dict) else None,
        video_stream_count=len([s for s in video_streams if s.get("codec_type") == "video"])
        if video_streams
        else (1 if video.video_codec else 0),
        audio_stream_count=len([s for s in video_streams if s.get("codec_type") == "audio"])
        if video_streams
        else (1 if video.audio_codec else 0),
        raw=raw if include_raw else None,
    )


def video_to_out(video: SourceVideo, include_raw: bool = False) -> SourceVideoOut:
    return SourceVideoOut(
        id=video.id,
        project_id=video.project_id,
        original_filename=video.original_filename,
        stored_path=video.stored_path,
        file_size_bytes=video.file_size_bytes,
        content_type=video.content_type,
        duration_seconds=video.duration_seconds,
        width=video.width,
        height=video.height,
        fps=video.fps,
        video_codec=video.video_codec,
        audio_codec=video.audio_codec,
        aspect_ratio=video.aspect_ratio,
        bitrate=video.bitrate,
        status=video.status,
        created_at=video.created_at,
        updated_at=video.updated_at,
        metadata=_metadata_out(video, include_raw=include_raw),
    )


def apply_metadata(video: SourceVideo, path: Path) -> SourceVideo:
    meta = extract_metadata(path)
    video.duration_seconds = meta.duration_seconds
    video.width = meta.width
    video.height = meta.height
    video.fps = meta.fps
    video.video_codec = meta.video_codec
    video.audio_codec = meta.audio_codec
    video.aspect_ratio = meta.aspect_ratio
    video.bitrate = meta.bitrate
    video.file_size_bytes = meta.file_size_bytes
    video.metadata_json = meta.raw
    video.status = "ready"
    return video


async def import_video_file(
    db: Session,
    *,
    project_id: str | None,
    project_name: str | None,
    upload: UploadFile,
) -> tuple[Project, SourceVideo]:
    filename = sanitize_filename(upload.filename or "upload.mp4")
    if not is_supported_video(filename):
        raise ValueError(
            f"Unsupported video format for '{filename}'. "
            "Supported: MP4, MOV, MKV, AVI, WEBM, and other common FFmpeg formats."
        )

    project: Project | None = None
    if project_id:
        project = db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
    else:
        name = (project_name or Path(filename).stem or "Untitled Project").strip()
        project = Project(name=name, status="active")
        db.add(project)
        db.flush()

    settings = get_settings()
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        temp_path = Path(tmp.name)
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)

    try:
        stored_path = store_uploaded_video(project.id, temp_path, filename, settings)
        video = SourceVideo(
            project_id=project.id,
            original_filename=filename,
            stored_path=str(stored_path),
            content_type=upload.content_type,
            status="processing_metadata",
        )
        db.add(video)
        db.flush()
        apply_metadata(video, stored_path)
        project.status = "active"
        db.commit()
        db.refresh(project)
        db.refresh(video)
        logger.info("Imported video %s into project %s", video.id, project.id)
        return project, video
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def get_video(db: Session, video_id: str) -> SourceVideo | None:
    return db.get(SourceVideo, video_id)


def list_videos(db: Session, project_id: str | None = None) -> list[SourceVideo]:
    stmt = select(SourceVideo).order_by(SourceVideo.created_at.desc())
    if project_id:
        stmt = stmt.where(SourceVideo.project_id == project_id)
    return list(db.scalars(stmt).all())


def refresh_video_metadata(db: Session, video_id: str) -> SourceVideo | None:
    video = db.get(SourceVideo, video_id)
    if not video:
        return None
    path = Path(video.stored_path)
    if not path.exists():
        raise FileNotFoundError(f"Stored video missing: {path}")
    apply_metadata(video, path)
    db.commit()
    db.refresh(video)
    return video


def delete_video(db: Session, video_id: str, delete_file: bool = True) -> bool:
    video = db.get(SourceVideo, video_id)
    if not video:
        return False
    stored = Path(video.stored_path)
    db.delete(video)
    db.commit()
    if delete_file and stored.exists():
        try:
            stored.unlink()
            parent = stored.parent
            if parent.exists() and not any(parent.iterdir()):
                shutil.rmtree(parent, ignore_errors=True)
        except OSError as exc:
            logger.warning("Failed to delete stored video file %s: %s", stored, exc)
    return True
