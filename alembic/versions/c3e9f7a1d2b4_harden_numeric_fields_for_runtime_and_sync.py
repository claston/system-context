"""harden numeric fields for runtime snapshot and sync run

Revision ID: c3e9f7a1d2b4
Revises: b1c7d4ef2a90
Create Date: 2026-04-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e9f7a1d2b4"
down_revision: Union[str, Sequence[str], None] = "b1c7d4ef2a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "runtime_snapshot",
        "pod_count",
        existing_type=sa.String(length=50),
        type_=sa.Integer(),
        postgresql_using="NULLIF(pod_count, '')::integer",
        existing_nullable=True,
    )
    op.alter_column(
        "runtime_snapshot",
        "restart_count",
        existing_type=sa.String(length=50),
        type_=sa.Integer(),
        postgresql_using="NULLIF(restart_count, '')::integer",
        existing_nullable=True,
    )
    op.alter_column(
        "sync_run",
        "records_processed",
        existing_type=sa.String(length=50),
        type_=sa.Integer(),
        postgresql_using="NULLIF(records_processed, '')::integer",
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "sync_run",
        "records_processed",
        existing_type=sa.Integer(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "runtime_snapshot",
        "restart_count",
        existing_type=sa.Integer(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "runtime_snapshot",
        "pod_count",
        existing_type=sa.Integer(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
