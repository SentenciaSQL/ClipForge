"""Helpers for serving local media files to the Angular video player."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

_MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".flac": "audio/flac",
    ".opus": "audio/opus",
}


def media_type_for(path: Path) -> str:
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def file_response_for_media(path: Path | str, *, download_name: str | None = None) -> FileResponse:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    name = download_name or file_path.name
    return FileResponse(
        path=file_path,
        media_type=media_type_for(file_path),
        filename=name,
        # Starlette FileResponse supports Range requests needed by HTML5 <video> seeking.
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )
