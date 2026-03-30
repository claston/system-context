from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SystemComponentCreate(BaseModel):
    name: str
    description: str | None = None


class SystemComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class CodeRepoCreate(BaseModel):
    system_component_id: UUID
    provider: str
    name: str
    url: str
    default_branch: str | None = None


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
    number: str
    title: str
    status: str = "open"
    author: str | None = None
    url: str | None = None
    merged_at: datetime | None = None


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
    sha: str
    message: str
    author: str | None = None
    committed_at: datetime | None = None


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
    environment: str
    version: str
    source: str | None = None
    status: str = "success"
    deployed_at: datetime | None = None


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
    environment: str
    captured_at: datetime | None = None
    pod_count: str | None = None
    restart_count: str | None = None
    health_status: str | None = None
    image_tag: str | None = None


class RuntimeSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system_component_id: UUID
    environment: str
    captured_at: datetime
    pod_count: str | None = None
    restart_count: str | None = None
    health_status: str | None = None
    image_tag: str | None = None
    created_at: datetime
    updated_at: datetime


class ApiContractCreate(BaseModel):
    system_component_id: UUID
    source: str
    version: str | None = None
    raw_location: str | None = None
    captured_at: datetime | None = None


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
    method: str
    path: str
    operation_id: str | None = None
    summary: str | None = None


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
    dependency_type: str = "http"
    confidence: str | None = None
    discovered_from: str | None = None
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
    connector_name: str
    status: str
    records_processed: str | None = None
    error_summary: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SyncRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    connector_name: str
    status: str
    records_processed: str | None = None
    error_summary: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentContextRequest(BaseModel):
    system_component_name: str
    environment: str | None = None


class AgentContextResponse(BaseModel):
    system_component: str
    environment: str | None = None
    latest_deployment_version: str | None = None
    latest_runtime_health: str | None = None
    recent_pull_requests: int
    recent_commits: int
    dependencies: list[str]
