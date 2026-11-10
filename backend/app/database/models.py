"""SQLAlchemy ORM models for AI Video Clipper."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    videos: Mapped[list[SourceVideo]] = relationship(back_populates="project", cascade="all, delete-orphan")
    clips: Mapped[list[Clip]] = relationship(back_populates="project", cascade="all, delete-orphan")
    jobs: Mapped[list[ProcessingJob]] = relationship(back_populates="project", cascade="all, delete-orphan")


class SourceVideo(Base):
    __tablename__ = "source_videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    content_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    video_codec: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    audio_codec: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    aspect_ratio: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    bitrate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="imported", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    project: Mapped[Project] = relationship(back_populates="videos")
    transcriptions: Mapped[list[Transcription]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    highlights: Mapped[list[Highlight]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    clips: Mapped[list[Clip]] = relationship(back_populates="video", cascade="all, delete-orphan")
    speakers: Mapped[list[Speaker]] = relationship(back_populates="video", cascade="all, delete-orphan")


class Transcription(Base):
    __tablename__ = "transcriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    video_id: Mapped[str] = mapped_column(ForeignKey("source_videos.id", ondelete="CASCADE"), nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    language_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), default="large-v3")
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    segments_json: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[SourceVideo] = relationship(back_populates="transcriptions")
    words: Mapped[list[TranscriptionWord]] = relationship(
        back_populates="transcription", cascade="all, delete-orphan"
    )


class TranscriptionWord(Base):
    __tablename__ = "transcription_words"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    transcription_id: Mapped[str] = mapped_column(
        ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False
    )
    word: Mapped[str] = mapped_column(String(512), nullable=False)
    start: Mapped[float] = mapped_column(Float, nullable=False)
    end: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speaker_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    index: Mapped[int] = mapped_column(Integer, default=0)

    transcription: Mapped[Transcription] = relationship(back_populates="words")


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    video_id: Mapped[str] = mapped_column(ForeignKey("source_videos.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    video: Mapped[SourceVideo] = relationship(back_populates="speakers")


class Highlight(Base):
    __tablename__ = "highlights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    video_id: Mapped[str] = mapped_column(ForeignKey("source_videos.id", ondelete="CASCADE"), nullable=False)
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    score_breakdown: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[SourceVideo] = relationship(back_populates="highlights")
    clips: Mapped[list[Clip]] = relationship(back_populates="highlight")


class SubtitlePreset(Base):
    __tablename__ = "subtitle_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    video_id: Mapped[str] = mapped_column(ForeignKey("source_videos.id", ondelete="CASCADE"), nullable=False)
    highlight_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("highlights.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subtitle_preset_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("subtitle_presets.id", ondelete="SET NULL"), nullable=True
    )
    reframing_mode: Mapped[str] = mapped_column(String(64), default="auto")
    output_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    preview_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    ass_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="draft")
    render_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    audio_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    project: Mapped[Project] = relationship(back_populates="clips")
    video: Mapped[SourceVideo] = relationship(back_populates="clips")
    highlight: Mapped[Optional[Highlight]] = relationship(back_populates="clips")
    subtitle_preset: Mapped[Optional[SubtitlePreset]] = relationship()
    audio_tracks: Mapped[list[AudioTrack]] = relationship(
        back_populates="clip", cascade="all, delete-orphan"
    )


class AudioTrack(Base):
    __tablename__ = "audio_tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    clip_id: Mapped[str] = mapped_column(ForeignKey("clips.id", ondelete="CASCADE"), nullable=False)
    track_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # original | music | replacement | voiceover
    label: Mapped[str] = mapped_column(String(128), default="Track")
    source_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    volume: Mapped[float] = mapped_column(Float, default=1.0)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    start_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    end_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    offset_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    fade_in_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    fade_out_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    loop: Mapped[bool] = mapped_column(Boolean, default=False)
    ducking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    clip: Mapped[Clip] = relationship(back_populates="audio_tracks")


class AudioPreset(Base):
    __tablename__ = "audio_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    video_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("source_videos.id", ondelete="SET NULL"), nullable=True
    )
    clip_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("clips.id", ondelete="SET NULL"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="queued")
    current_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stages_json: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    result_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Optional[Project]] = relationship(back_populates="jobs")


class AppSettings(Base):
    __tablename__ = "app_settings"
    __table_args__ = (UniqueConstraint("key", name="uq_app_settings_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
