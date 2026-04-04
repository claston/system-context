"""add connector sync state and raw event identity

Revision ID: e2f4c6a8b0d1
Revises: d9a4c2e7f1b0
Create Date: 2026-04-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f4c6a8b0d1"
down_revision: Union[str, Sequence[str], None] = "d9a4c2e7f1b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "connector_raw_event",
        sa.Column("target_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "connector_raw_event",
        sa.Column("source_key", sa.String(length=512), nullable=True),
    )

    op.execute(
        """
        UPDATE connector_raw_event
        SET
            target_key = COALESCE(payload->>'repository', '__global__'),
            source_key = COALESCE(
                payload->>'source_key',
                COALESCE(payload->>'kind', 'item') || ':legacy:' || id::text
            )
        WHERE target_key IS NULL OR source_key IS NULL
        """
    )

    op.alter_column("connector_raw_event", "target_key", nullable=False)
    op.alter_column("connector_raw_event", "source_key", nullable=False)
    op.create_unique_constraint(
        "connector_raw_event_identity_key",
        "connector_raw_event",
        ["connector_name", "target_key", "source_key"],
    )

    op.create_table(
        "connector_sync_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector_name", sa.String(length=100), nullable=False),
        sa.Column("target_key", sa.String(length=255), nullable=False),
        sa.Column("last_cursor", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connector_name",
            "target_key",
            name="connector_sync_state_connector_target_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("connector_sync_state")
    op.drop_constraint(
        "connector_raw_event_identity_key",
        "connector_raw_event",
        type_="unique",
    )
    op.drop_column("connector_raw_event", "source_key")
    op.drop_column("connector_raw_event", "target_key")
