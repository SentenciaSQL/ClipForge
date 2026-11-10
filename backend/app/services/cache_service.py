"""Workspace cache inventory and invalidation."""

from __future__ import annotations

import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CacheKind = Literal["transcription", "renders", "audio_extract", "all"]


@dataclass
class CacheEntry:
    kind: str
    path: str
    size_bytes: int
    mtime: float
    video_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _dir_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def _iter_video_temp_roots() -> list[Path]:
    settings = get_settings()
    root = settings.temporary_dir
    if not root.exists():
        return []
    return [p for p in root.iterdir() if p.is_dir()]


def inventory(kind: CacheKind = "all") -> dict[str, Any]:
    entries: list[CacheEntry] = []
    for video_dir in _iter_video_temp_roots():
        video_id = video_dir.name
        mapping = {
            "transcription": video_dir / "transcription_cache",
            "renders": video_dir / "renders",
            "audio_extract": video_dir / "audio",
        }
        for cache_kind, path in mapping.items():
            if kind not in {"all", cache_kind}:
                continue
            if not path.exists():
                continue
            size = _dir_size(path)
            if size <= 0 and not any(path.rglob("*")):
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            entries.append(
                CacheEntry(
                    kind=cache_kind,
                    path=str(path),
                    size_bytes=size,
                    mtime=mtime,
                    video_id=video_id,
                )
            )

    total = sum(item.size_bytes for item in entries)
    by_kind: dict[str, int] = {}
    for item in entries:
        by_kind[item.kind] = by_kind.get(item.kind, 0) + item.size_bytes
    return {
        "total_bytes": total,
        "entry_count": len(entries),
        "by_kind": by_kind,
        "entries": [item.to_dict() for item in sorted(entries, key=lambda e: e.mtime, reverse=True)],
    }


def clear_cache(
    *,
    kind: CacheKind = "all",
    video_id: str | None = None,
    older_than_hours: float | None = None,
) -> dict[str, Any]:
    removed = 0
    freed = 0
    cutoff = None
    if older_than_hours is not None and older_than_hours > 0:
        cutoff = time.time() - (older_than_hours * 3600)

    for video_dir in _iter_video_temp_roots():
        if video_id and video_dir.name != video_id:
            continue
        targets: list[tuple[str, Path]] = [
            ("transcription", video_dir / "transcription_cache"),
            ("renders", video_dir / "renders"),
            ("audio_extract", video_dir / "audio"),
        ]
        for cache_kind, path in targets:
            if kind not in {"all", cache_kind}:
                continue
            if not path.exists():
                continue
            if cutoff is not None:
                try:
                    if path.stat().st_mtime > cutoff:
                        continue
                except OSError:
                    continue
            size = _dir_size(path)
            try:
                shutil.rmtree(path)
                removed += 1
                freed += size
                logger.info("Cleared cache %s (%s bytes)", path, size)
            except OSError as exc:
                logger.warning("Failed to clear %s: %s", path, exc)

    return {"removed_paths": removed, "freed_bytes": freed, "kind": kind, "video_id": video_id}


def invalidate_transcription_cache(video_id: str) -> dict[str, Any]:
    return clear_cache(kind="transcription", video_id=video_id)
