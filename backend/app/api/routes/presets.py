"""Subtitle preset listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import SubtitlePreset

router = APIRouter()


@router.get("/subtitle-presets")
def list_subtitle_presets(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(SubtitlePreset).order_by(SubtitlePreset.name.asc())).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "config": row.config_json,
            "is_builtin": row.is_builtin,
        }
        for row in rows
    ]
