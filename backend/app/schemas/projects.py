"""Project schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None


class ProjectOut(ORMModel):
    id: str
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    video_count: int = 0
    clip_count: int = 0
