"""Reusable export profiles (TikTok, Reels, Shorts, custom)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ExportProfile
from app.schemas.clip_config import ClipConfiguration, ExportProfileIn, ExportProfileOut, ExportProfileUpdate
from app.core.logging import get_logger

logger = get_logger(__name__)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "profile"


def _out(row: ExportProfile) -> ExportProfileOut:
    return ExportProfileOut(
        id=row.id,
        name=row.name,
        slug=row.slug,
        description=row.description,
        config_json=dict(row.config_json or {}),
        is_builtin=bool(row.is_builtin),
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def builtin_profiles() -> list[dict]:
    def cfg(**video_overrides) -> dict:
        base = ClipConfiguration().model_dump()
        base["video"].update(video_overrides)
        return ClipConfiguration.model_validate(base).model_dump()

    return [
        {
            "name": "TikTok 1080x1920",
            "slug": "tiktok-1080x1920",
            "description": "Vertical 9:16 for TikTok",
            "config_json": cfg(aspect_ratio="9:16", resolution_label="1080p", width=1080, height=1920, fps=30),
        },
        {
            "name": "Instagram Reels 1080x1920",
            "slug": "instagram-reels-1080x1920",
            "description": "Vertical 9:16 for Reels",
            "config_json": cfg(aspect_ratio="9:16", resolution_label="1080p", width=1080, height=1920, fps=30),
        },
        {
            "name": "YouTube Shorts 1080x1920",
            "slug": "youtube-shorts-1080x1920",
            "description": "Vertical 9:16 for Shorts",
            "config_json": cfg(aspect_ratio="9:16", resolution_label="1080p", width=1080, height=1920, fps=30),
        },
        {
            "name": "Instagram Square 1080x1080",
            "slug": "instagram-square-1080x1080",
            "description": "Square 1:1 feed post",
            "config_json": cfg(aspect_ratio="1:1", resolution_label="1080p", width=1080, height=1080, fps=30),
        },
        {
            "name": "YouTube Landscape 1920x1080",
            "slug": "youtube-landscape-1920x1080",
            "description": "Landscape 16:9",
            "config_json": cfg(aspect_ratio="16:9", resolution_label="1080p", width=1920, height=1080, fps=30),
        },
    ]


def seed_export_profiles(db: Session) -> None:
    for item in builtin_profiles():
        existing = db.scalar(select(ExportProfile).where(ExportProfile.slug == item["slug"]))
        if existing:
            existing.name = item["name"]
            existing.description = item["description"]
            existing.config_json = item["config_json"]
            existing.is_builtin = True
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(
                ExportProfile(
                    name=item["name"],
                    slug=item["slug"],
                    description=item["description"],
                    config_json=item["config_json"],
                    is_builtin=True,
                )
            )
    db.commit()
    logger.info("Export profiles seeded")


def list_profiles(db: Session) -> list[ExportProfileOut]:
    rows = list(db.scalars(select(ExportProfile).order_by(ExportProfile.name.asc())).all())
    return [_out(row) for row in rows]


def create_profile(db: Session, payload: ExportProfileIn) -> ExportProfileOut:
    slug = payload.slug or _slugify(payload.name)
    existing = db.scalar(select(ExportProfile).where(ExportProfile.slug == slug))
    if existing:
        raise ValueError(f"Profile slug already exists: {slug}")
    row = ExportProfile(
        name=payload.name,
        slug=slug,
        description=payload.description,
        config_json=payload.config_json.model_dump(),
        is_builtin=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


def update_profile(db: Session, profile_id: str, payload: ExportProfileUpdate) -> ExportProfileOut:
    row = db.get(ExportProfile, profile_id)
    if not row:
        raise LookupError("Export profile not found")
    if row.is_builtin and payload.config_json is None and payload.name is None:
        pass
    if row.is_builtin and payload.name:
        # Allow description/config edits on builtins but keep slug.
        pass
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        row.name = data["name"]
    if "description" in data:
        row.description = data["description"]
    if "config_json" in data and data["config_json"] is not None:
        row.config_json = data["config_json"]
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _out(row)


def delete_profile(db: Session, profile_id: str) -> None:
    row = db.get(ExportProfile, profile_id)
    if not row:
        raise LookupError("Export profile not found")
    if row.is_builtin:
        raise PermissionError("Built-in profiles cannot be deleted")
    db.delete(row)
    db.commit()


def get_profile(db: Session, profile_id: str) -> ExportProfile:
    row = db.get(ExportProfile, profile_id)
    if not row:
        raise LookupError("Export profile not found")
    return row
