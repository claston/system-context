import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class SystemComponent(Base):
    __tablename__ = "system_component"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(String(1000), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CodeRepo(Base):
    __tablename__ = "code_repo"
    __table_args__ = (
        UniqueConstraint("provider", "name", name="code_repo_provider_name_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_component_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_component.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    url = Column(String(1000), nullable=False)
    default_branch = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PullRequest(Base):
    __tablename__ = "pull_request"
    __table_args__ = (
        UniqueConstraint("code_repo_id", "number", name="pull_request_repo_number_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_repo_id = Column(UUID(as_uuid=True), ForeignKey("code_repo.id", ondelete="CASCADE"), nullable=False)
    number = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="open")
    author = Column(String(255), nullable=True)
    url = Column(String(1000), nullable=True)
    merged_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Commit(Base):
    __tablename__ = "commit"
    __table_args__ = (
        UniqueConstraint("code_repo_id", "sha", name="commit_repo_sha_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_repo_id = Column(UUID(as_uuid=True), ForeignKey("code_repo.id", ondelete="CASCADE"), nullable=False)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_request.id", ondelete="SET NULL"), nullable=True)
    sha = Column(String(128), nullable=False)
    message = Column(String(1000), nullable=False)
    author = Column(String(255), nullable=True)
    committed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Deployment(Base):
    __tablename__ = "deployment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_component_id = Column(UUID(as_uuid=True), ForeignKey("system_component.id", ondelete="CASCADE"), nullable=False)
    environment = Column(String(100), nullable=False)
    version = Column(String(255), nullable=False)
    source = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="success")
    deployed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class RuntimeSnapshot(Base):
    __tablename__ = "runtime_snapshot"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_component_id = Column(UUID(as_uuid=True), ForeignKey("system_component.id", ondelete="CASCADE"), nullable=False)
    environment = Column(String(100), nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    pod_count = Column(Integer, nullable=True)
    restart_count = Column(Integer, nullable=True)
    health_status = Column(String(50), nullable=True)
    image_tag = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ApiContract(Base):
    __tablename__ = "api_contract"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_component_id = Column(UUID(as_uuid=True), ForeignKey("system_component.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(255), nullable=False)
    version = Column(String(255), nullable=True)
    raw_location = Column(String(1000), nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Endpoint(Base):
    __tablename__ = "endpoint"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_contract_id = Column(UUID(as_uuid=True), ForeignKey("api_contract.id", ondelete="CASCADE"), nullable=False)
    method = Column(String(20), nullable=False)
    path = Column(String(1000), nullable=False)
    operation_id = Column(String(255), nullable=True)
    summary = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Dependency(Base):
    __tablename__ = "dependency"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_system_component_id = Column(UUID(as_uuid=True), ForeignKey("system_component.id", ondelete="CASCADE"), nullable=False)
    target_system_component_id = Column(UUID(as_uuid=True), ForeignKey("system_component.id", ondelete="CASCADE"), nullable=False)
    dependency_type = Column(String(100), nullable=False, default="http")
    confidence = Column(String(50), nullable=True)
    discovered_from = Column(String(100), nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SyncRun(Base):
    __tablename__ = "sync_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connector_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    records_processed = Column(Integer, nullable=True)
    error_summary = Column(String(1000), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ConnectorRawEvent(Base):
    __tablename__ = "connector_raw_event"
    __table_args__ = (
        UniqueConstraint(
            "connector_name",
            "target_key",
            "source_key",
            name="connector_raw_event_identity_key",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sync_run_id = Column(UUID(as_uuid=True), ForeignKey("sync_run.id", ondelete="CASCADE"), nullable=False)
    connector_name = Column(String(100), nullable=False)
    target_key = Column(String(255), nullable=False)
    source_key = Column(String(512), nullable=False)
    payload = Column(JSON, nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ConnectorSyncState(Base):
    __tablename__ = "connector_sync_state"
    __table_args__ = (
        UniqueConstraint(
            "connector_name",
            "target_key",
            name="connector_sync_state_connector_target_key",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connector_name = Column(String(100), nullable=False)
    target_key = Column(String(255), nullable=False)
    last_cursor = Column(String(100), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
