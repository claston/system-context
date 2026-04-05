"""add integration target mapping table

Revision ID: f4b1d23c9a10
Revises: e2f4c6a8b0d1
Create Date: 2026-04-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4b1d23c9a10"
down_revision: Union[str, Sequence[str], None] = "e2f4c6a8b0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_target_mapping",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector_name", sa.String(length=100), nullable=False),
        sa.Column("external_target_id", sa.String(length=255), nullable=False),
        sa.Column("external_target_name", sa.String(length=255), nullable=True),
        sa.Column("system_component_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["system_component_id"],
            ["system_component.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connector_name",
            "external_target_id",
            "environment",
            name="integration_target_mapping_connector_target_environment_key",
        ),
    )
    op.create_index(
        "integration_target_mapping_lookup_idx",
        "integration_target_mapping",
        ["connector_name", "environment", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "integration_target_mapping_lookup_idx",
        table_name="integration_target_mapping",
    )
    op.drop_table("integration_target_mapping")
