"""add operational issue table

Revision ID: 9c1a2d3e4f50
Revises: f4b1d23c9a10
Create Date: 2026-04-09 12:35:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c1a2d3e4f50"
down_revision: Union[str, Sequence[str], None] = "f4b1d23c9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operational_issue",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("system_component_id", sa.UUID(), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False),
        sa.Column("issue_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_source", sa.String(length=100), nullable=True),
        sa.Column("evidence_payload", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["system_component_id"], ["system_component.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("operational_issue")
