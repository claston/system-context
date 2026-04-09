"""add context chunk table

Revision ID: b2d3e4f5a6b7
Revises: 9c1a2d3e4f50
Create Date: 2026-04-09 18:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "9c1a2d3e4f50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "context_chunk",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("system_component_name", sa.String(length=255), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=True),
        sa.Column("chunk_text", sa.String(length=4000), nullable=False),
        sa.Column("chunk_hash", sa.String(length=128), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_hash", name="context_chunk_chunk_hash_key"),
    )
    op.create_index(
        "context_chunk_component_env_captured_idx",
        "context_chunk",
        ["system_component_name", "environment", "captured_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("context_chunk_component_env_captured_idx", table_name="context_chunk")
    op.drop_table("context_chunk")

