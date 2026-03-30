"""rename service table to system_component

Revision ID: 7d2f4f9c1a3b
Revises: ab55e864a5c5
Create Date: 2026-03-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d2f4f9c1a3b"
down_revision: Union[str, Sequence[str], None] = "ab55e864a5c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("service", "system_component")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE system_component RENAME CONSTRAINT "
            "service_name_key TO system_component_name_key"
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE system_component RENAME CONSTRAINT "
            "system_component_name_key TO service_name_key"
        )
    op.rename_table("system_component", "service")
