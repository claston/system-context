from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f92d1b6e11"
down_revision: Union[str, Sequence[str], None] = "7d2f4f9c1a3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "code_repo",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("system_component_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["system_component_id"],
            ["system_component.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "name", name="code_repo_provider_name_key"),
    )
    op.create_index("ix_code_repo_system_component_id", "code_repo", ["system_component_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_code_repo_system_component_id", table_name="code_repo")
    op.drop_table("code_repo")
