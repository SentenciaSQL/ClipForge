"""Initial schema for AI Video Clipper.

Revision ID: 20260324_0001
Revises:
Create Date: 2026-03-24 00:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260324_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "subtitle_presets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "audio_presets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "app_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("key", name="uq_app_settings_key"),
    )
    op.create_table(
        "source_videos",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("stored_path", sa.String(length=1024), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column("video_codec", sa.String(length=64), nullable=True),
        sa.Column("audio_codec", sa.String(length=64), nullable=True),
        sa.Column("aspect_ratio", sa.String(length=32), nullable=True),
        sa.Column("bitrate", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "transcriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("video_id", sa.String(length=36), sa.ForeignKey("source_videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("language_probability", sa.Float(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("segments_json", sa.JSON(), nullable=True),
        sa.Column("audio_path", sa.String(length=1024), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "transcription_words",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("transcription_id", sa.String(length=36), sa.ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("word", sa.String(length=512), nullable=False),
        sa.Column("start", sa.Float(), nullable=False),
        sa.Column("end", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("speaker_id", sa.String(length=36), nullable=True),
        sa.Column("index", sa.Integer(), nullable=False),
    )
    op.create_table(
        "speakers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("video_id", sa.String(length=36), sa.ForeignKey("source_videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_table(
        "highlights",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("video_id", sa.String(length=36), sa.ForeignKey("source_videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_seconds", sa.Float(), nullable=False),
        sa.Column("end_seconds", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("hook", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "clips",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("video_id", sa.String(length=36), sa.ForeignKey("source_videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("highlight_id", sa.String(length=36), sa.ForeignKey("highlights.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("start_seconds", sa.Float(), nullable=False),
        sa.Column("end_seconds", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("hook", sa.Text(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("subtitle_preset_id", sa.String(length=36), sa.ForeignKey("subtitle_presets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reframing_mode", sa.String(length=64), nullable=False),
        sa.Column("output_path", sa.String(length=1024), nullable=True),
        sa.Column("preview_path", sa.String(length=1024), nullable=True),
        sa.Column("ass_path", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("render_settings", sa.JSON(), nullable=True),
        sa.Column("audio_config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audio_tracks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("clip_id", sa.String(length=36), sa.ForeignKey("clips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("track_type", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("source_path", sa.String(length=1024), nullable=True),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("muted", sa.Boolean(), nullable=False),
        sa.Column("start_seconds", sa.Float(), nullable=False),
        sa.Column("end_seconds", sa.Float(), nullable=True),
        sa.Column("offset_seconds", sa.Float(), nullable=False),
        sa.Column("fade_in_seconds", sa.Float(), nullable=False),
        sa.Column("fade_out_seconds", sa.Float(), nullable=False),
        sa.Column("loop", sa.Boolean(), nullable=False),
        sa.Column("ducking_enabled", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("video_id", sa.String(length=36), sa.ForeignKey("source_videos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("clip_id", sa.String(length=36), sa.ForeignKey("clips.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("stages_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("processing_jobs")
    op.drop_table("audio_tracks")
    op.drop_table("clips")
    op.drop_table("highlights")
    op.drop_table("speakers")
    op.drop_table("transcription_words")
    op.drop_table("transcriptions")
    op.drop_table("source_videos")
    op.drop_table("app_settings")
    op.drop_table("audio_presets")
    op.drop_table("subtitle_presets")
    op.drop_table("projects")
