"""Add generation_config on videos and generation_profiles table.

Revision ID: 20261111_0003
Revises: 20261111_0002
Create Date: 2026-11-11 01:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261111_0003"
down_revision: Union[str, None] = "20261111_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("source_videos") as batch:
        batch.add_column(sa.Column("generation_config_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("thumbnail_path", sa.String(length=1024), nullable=True))

    op.create_table(
        "generation_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )


def downgrade() -> None:
    op.drop_table("generation_profiles")
    with op.batch_alter_table("source_videos") as batch:
        batch.drop_column("thumbnail_path")
        batch.drop_column("generation_config_json")
