"""Seed built-in subtitle presets and default settings."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import SubtitlePreset

logger = get_logger(__name__)


def _preset_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "resources" / "subtitle-presets"


def seed_subtitle_presets(db: Session) -> None:
    preset_dir = _preset_dir()
    if not preset_dir.exists():
        logger.warning("Subtitle preset directory missing: %s", preset_dir)
        return

    for path in sorted(preset_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping invalid preset %s: %s", path.name, exc)
            continue

        slug = data.get("slug") or path.stem
        existing = db.scalar(select(SubtitlePreset).where(SubtitlePreset.slug == slug))
        if existing:
            existing.name = data.get("name", existing.name)
            existing.config_json = data
            existing.is_builtin = True
        else:
            db.add(
                SubtitlePreset(
                    name=data.get("name", slug),
                    slug=slug,
                    config_json=data,
                    is_builtin=True,
                )
            )
    db.commit()
    logger.info("Subtitle presets seeded from %s", preset_dir)
