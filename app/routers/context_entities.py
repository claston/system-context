from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_context_entity_repository, get_sync_repository
from app.repositories import (
    ContextEntityReferenceNotFoundError,
    DuplicateContextEntityError,
)
from app.schemas import (
    ApiContractCreate,
    ApiContractResponse,
    CommitCreate,
    CommitResponse,
    DependencyCreate,
    DependencyResponse,
    DeploymentCreate,
    DeploymentResponse,
    EndpointCreate,
    EndpointResponse,
    PullRequestCreate,
    PullRequestResponse,
    RuntimeSnapshotCreate,
    RuntimeSnapshotResponse,
    SyncRunCreate,
    SyncRunResponse,
)

router = APIRouter()


def _drop_optional_datetime(payload: dict, field: str) -> dict:
    if not payload.get(field):
        payload.pop(field, None)
    return payload


@router.post("/pull-requests", response_model=PullRequestResponse)
def create_pull_request(
    payload: PullRequestCreate,
    context_repo=Depends(get_context_entity_repository),
):
    data = payload.model_dump()
    if data.get("url"):
        data["url"] = str(data["url"])
    try:
        return context_repo.create_pull_request(**data)
    except ContextEntityReferenceNotFoundError:
        raise HTTPException(status_code=404, detail="Referenced resource not found")
    except DuplicateContextEntityError:
        raise HTTPException(status_code=409, detail="Resource already exists")


@router.get("/pull-requests", response_model=list[PullRequestResponse])
def list_pull_requests(context_repo=Depends(get_context_entity_repository)):
    return context_repo.list_pull_requests()


@router.post("/commits", response_model=CommitResponse)
def create_commit(payload: CommitCreate, context_repo=Depends(get_context_entity_repository)):
    data = _drop_optional_datetime(payload.model_dump(), "committed_at")
    try:
        return context_repo.create_commit(**data)
    except ContextEntityReferenceNotFoundError:
        raise HTTPException(status_code=404, detail="Referenced resource not found")
    except DuplicateContextEntityError:
        raise HTTPException(status_code=409, detail="Resource already exists")


@router.get("/commits", response_model=list[CommitResponse])
def list_commits(context_repo=Depends(get_context_entity_repository)):
    return context_repo.list_commits()


@router.post("/deployments", response_model=DeploymentResponse)
def create_deployment(
    payload: DeploymentCreate,
    context_repo=Depends(get_context_entity_repository),
):
    data = _drop_optional_datetime(payload.model_dump(), "deployed_at")
    try:
        return context_repo.create_deployment(**data)
    except ContextEntityReferenceNotFoundError:
        raise HTTPException(status_code=404, detail="Referenced resource not found")
    except DuplicateContextEntityError:
        raise HTTPException(status_code=409, detail="Resource already exists")


@router.get("/deployments", response_model=list[DeploymentResponse])
def list_deployments(context_repo=Depends(get_context_entity_repository)):
    return context_repo.list_deployments()


@router.post("/runtime-snapshots", response_model=RuntimeSnapshotResponse)
def create_runtime_snapshot(
    payload: RuntimeSnapshotCreate,
    context_repo=Depends(get_context_entity_repository),
):
    data = _drop_optional_datetime(payload.model_dump(), "captured_at")
    try:
        return context_repo.create_runtime_snapshot(**data)
    except ContextEntityReferenceNotFoundError:
        raise HTTPException(status_code=404, detail="Referenced resource not found")
    except DuplicateContextEntityError:
        raise HTTPException(status_code=409, detail="Resource already exists")


@router.get("/runtime-snapshots", response_model=list[RuntimeSnapshotResponse])
def list_runtime_snapshots(context_repo=Depends(get_context_entity_repository)):
    return context_repo.list_runtime_snapshots()


@router.post("/api-contracts", response_model=ApiContractResponse)
def create_api_contract(
    payload: ApiContractCreate,
    context_repo=Depends(get_context_entity_repository),
):
    data = _drop_optional_datetime(payload.model_dump(), "captured_at")
    if data.get("raw_location"):
        data["raw_location"] = str(data["raw_location"])
    try:
        return context_repo.create_api_contract(**data)
    except ContextEntityReferenceNotFoundError:
        raise HTTPException(status_code=404, detail="Referenced resource not found")
    except DuplicateContextEntityError:
        raise HTTPException(status_code=409, detail="Resource already exists")


@router.get("/api-contracts", response_model=list[ApiContractResponse])
def list_api_contracts(context_repo=Depends(get_context_entity_repository)):
    return context_repo.list_api_contracts()


@router.post("/endpoints", response_model=EndpointResponse)
def create_endpoint(payload: EndpointCreate, context_repo=Depends(get_context_entity_repository)):
    try:
        return context_repo.create_endpoint(**payload.model_dump())
    except ContextEntityReferenceNotFoundError:
        raise HTTPException(status_code=404, detail="Referenced resource not found")
    except DuplicateContextEntityError:
        raise HTTPException(status_code=409, detail="Resource already exists")


@router.get("/endpoints", response_model=list[EndpointResponse])
def list_endpoints(context_repo=Depends(get_context_entity_repository)):
    return context_repo.list_endpoints()


@router.post("/dependencies", response_model=DependencyResponse)
def create_dependency(
    payload: DependencyCreate,
    context_repo=Depends(get_context_entity_repository),
):
    data = _drop_optional_datetime(payload.model_dump(), "captured_at")
    try:
        return context_repo.create_dependency(**data)
    except ContextEntityReferenceNotFoundError:
        raise HTTPException(status_code=404, detail="Referenced resource not found")
    except DuplicateContextEntityError:
        raise HTTPException(status_code=409, detail="Resource already exists")


@router.get("/dependencies", response_model=list[DependencyResponse])
def list_dependencies(context_repo=Depends(get_context_entity_repository)):
    return context_repo.list_dependencies()


@router.post("/sync-runs", response_model=SyncRunResponse)
def create_sync_run(payload: SyncRunCreate, sync_repo=Depends(get_sync_repository)):
    data = _drop_optional_datetime(payload.model_dump(), "started_at")
    try:
        return sync_repo.create_sync_run(**data)
    except ContextEntityReferenceNotFoundError:
        raise HTTPException(status_code=404, detail="Referenced resource not found")
    except DuplicateContextEntityError:
        raise HTTPException(status_code=409, detail="Resource already exists")


@router.get("/sync-runs", response_model=list[SyncRunResponse])
def list_sync_runs(sync_repo=Depends(get_sync_repository)):
    return sync_repo.list_sync_runs()
