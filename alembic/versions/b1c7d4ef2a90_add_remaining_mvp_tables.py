"""add remaining mvp tables

Revision ID: b1c7d4ef2a90
Revises: a3f92d1b6e11
Create Date: 2026-03-30 01:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c7d4ef2a90"
down_revision: Union[str, Sequence[str], None] = "a3f92d1b6e11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pull_request",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code_repo_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["code_repo_id"], ["code_repo.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_repo_id", "number", name="pull_request_repo_number_key"),
    )

    op.create_table(
        "commit",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code_repo_id", sa.UUID(), nullable=False),
        sa.Column("pull_request_id", sa.UUID(), nullable=True),
        sa.Column("sha", sa.String(length=128), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["code_repo_id"], ["code_repo.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pull_request_id"], ["pull_request.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_repo_id", "sha", name="commit_repo_sha_key"),
    )

    op.create_table(
        "deployment",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("system_component_id", sa.UUID(), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_component_id"], ["system_component.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "runtime_snapshot",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("system_component_id", sa.UUID(), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pod_count", sa.String(length=50), nullable=True),
        sa.Column("restart_count", sa.String(length=50), nullable=True),
        sa.Column("health_status", sa.String(length=50), nullable=True),
        sa.Column("image_tag", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_component_id"], ["system_component.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "api_contract",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("system_component_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=255), nullable=True),
        sa.Column("raw_location", sa.String(length=1000), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_component_id"], ["system_component.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "endpoint",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("api_contract_id", sa.UUID(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("operation_id", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_contract_id"], ["api_contract.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dependency",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_system_component_id", sa.UUID(), nullable=False),
        sa.Column("target_system_component_id", sa.UUID(), nullable=False),
        sa.Column("dependency_type", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.String(length=50), nullable=True),
        sa.Column("discovered_from", sa.String(length=100), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_system_component_id"], ["system_component.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_system_component_id"], ["system_component.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sync_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("connector_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("records_processed", sa.String(length=50), nullable=True),
        sa.Column("error_summary", sa.String(length=1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sync_run")
    op.drop_table("dependency")
    op.drop_table("endpoint")
    op.drop_table("api_contract")
    op.drop_table("runtime_snapshot")
    op.drop_table("deployment")
    op.drop_table("commit")
    op.drop_table("pull_request")
