from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

AllowedProvider = Literal["github", "gitlab", "bitbucket", "azuredevops"]
PullRequestStatus = Literal["open", "closed", "merged"]
DeploymentStatus = Literal["success", "failed", "in_progress", "rolled_back"]
EndpointMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
DependencyType = Literal["http", "grpc", "event", "database", "queue", "other"]
SyncRunStatus = Literal["success", "failed", "running", "partial"]


def _normalize_non_empty(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


class SystemComponentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_non_empty(value)


class SystemComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class CodeRepoCreate(BaseModel):
    system_component_id: UUID
    provider: AllowedProvider
    name: str = Field(min_length=1, max_length=255)
    url: HttpUrl
    default_branch: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_non_empty(value)

    @field_validator("default_branch")
    @classmethod
    def validate_default_branch(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_non_empty(value)


class CodeRepoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system_component_id: UUID
    provider: str
    name: str
    url: str
    default_branch: str | None = None
    created_at: datetime
    updated_at: datetime


class PullRequestCreate(BaseModel):
    code_repo_id: UUID
    number: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=500)
    status: PullRequestStatus = "open"
    author: str | None = Field(default=None, max_length=255)
    url: HttpUrl | None = None
    merged_at: datetime | None = None

    @field_validator("number", "title")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _normalize_non_empty(value)


class PullRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code_repo_id: UUID
    number: str
    title: str
    status: str
    author: str | None = None
    url: str | None = None
    merged_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CommitCreate(BaseModel):
    code_repo_id: UUID
    pull_request_id: UUID | None = None
    sha: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=1000)
    author: str | None = Field(default=None, max_length=255)
    committed_at: datetime | None = None

    @field_validator("sha", "message")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _normalize_non_empty(value)


class CommitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code_repo_id: UUID
    pull_request_id: UUID | None = None
    sha: str
    message: str
    author: str | None = None
    committed_at: datetime
    created_at: datetime
    updated_at: datetime


class DeploymentCreate(BaseModel):
    system_component_id: UUID
    environment: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=255)
    source: str | None = Field(default=None, max_length=100)
    status: DeploymentStatus = "success"
    deployed_at: datetime | None = None

    @field_validator("environment", "version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _normalize_non_empty(value)


class DeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system_component_id: UUID
    environment: str
    version: str
    source: str | None = None
    status: str
    deployed_at: datetime
    created_at: datetime
    updated_at: datetime


class RuntimeSnapshotCreate(BaseModel):
    system_component_id: UUID
    environment: str = Field(min_length=1, max_length=100)
    captured_at: datetime | None = None
    pod_count: int | None = Field(default=None, ge=0)
    restart_count: int | None = Field(default=None, ge=0)
    health_status: str | None = Field(default=None, max_length=50)
    image_tag: str | None = Field(default=None, max_length=255)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        return _normalize_non_empty(value)


class RuntimeSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system_component_id: UUID
    environment: str
    captured_at: datetime
    pod_count: int | None = None
    restart_count: int | None = None
    health_status: str | None = None
    image_tag: str | None = None
    created_at: datetime
    updated_at: datetime


class ApiContractCreate(BaseModel):
    system_component_id: UUID
    source: str = Field(min_length=1, max_length=255)
    version: str | None = Field(default=None, max_length=255)
    raw_location: HttpUrl | None = None
    captured_at: datetime | None = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        return _normalize_non_empty(value)


class ApiContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system_component_id: UUID
    source: str
    version: str | None = None
    raw_location: str | None = None
    captured_at: datetime
    created_at: datetime
    updated_at: datetime


class EndpointCreate(BaseModel):
    api_contract_id: UUID
    method: EndpointMethod
    path: str = Field(min_length=1, max_length=1000)
    operation_id: str | None = Field(default=None, max_length=255)
    summary: str | None = Field(default=None, max_length=1000)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _normalize_non_empty(value)


class EndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    api_contract_id: UUID
    method: str
    path: str
    operation_id: str | None = None
    summary: str | None = None
    created_at: datetime
    updated_at: datetime


class DependencyCreate(BaseModel):
    source_system_component_id: UUID
    target_system_component_id: UUID
    dependency_type: DependencyType = "http"
    confidence: str | None = Field(default=None, max_length=50)
    discovered_from: str | None = Field(default=None, max_length=100)
    captured_at: datetime | None = None


class DependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_system_component_id: UUID
    target_system_component_id: UUID
    dependency_type: str
    confidence: str | None = None
    discovered_from: str | None = None
    captured_at: datetime
    created_at: datetime
    updated_at: datetime


class SyncRunCreate(BaseModel):
    connector_name: str = Field(min_length=1, max_length=100)
    status: SyncRunStatus
    records_processed: int | None = Field(default=None, ge=0)
    error_summary: str | None = Field(default=None, max_length=1000)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator("connector_name")
    @classmethod
    def validate_connector_name(cls, value: str) -> str:
        return _normalize_non_empty(value)

    @model_validator(mode="after")
    def validate_time_window(self):
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished_at must be greater than or equal to started_at")
        if self.status == "success" and self.error_summary:
            raise ValueError("error_summary must be empty when status is success")
        return self


class SyncRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    connector_name: str
    status: str
    records_processed: int | None = None
    error_summary: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SyncRunTriggerRequest(BaseModel):
    system_component_name: str | None = Field(default=None, max_length=255)

    @field_validator("system_component_name")
    @classmethod
    def validate_system_component_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_non_empty(value)


class GithubNormalizationResponse(BaseModel):
    sync_run_id: UUID
    connector_name: str
    raw_events_read: int
    pull_requests_created: int
    pull_requests_updated: int
    commits_created: int
    commits_updated: int
    skipped: int
    errors: list[str]


class AgentContextRequest(BaseModel):
    system_component_name: str = Field(min_length=1, max_length=255)
    environment: str | None = Field(default=None, max_length=100)

    @field_validator("system_component_name")
    @classmethod
    def validate_component_name(cls, value: str) -> str:
        return _normalize_non_empty(value)


class AgentContextResponse(BaseModel):
    system_component: str
    environment: str | None = None
    latest_deployment_version: str | None = None
    latest_runtime_health: str | None = None
    recent_pull_requests: int
    recent_commits: int
    dependencies: list[str]
