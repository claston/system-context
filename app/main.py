from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.application import (
    CodeRepoNotFoundError,
    CodeRepoService,
    ContextService,
    SystemComponentNotFoundError,
    SystemComponentService,
)
from app.db import SessionLocal
from app.models import SystemComponent
from app.repositories import (
    DuplicateCodeRepoError,
    DuplicateSystemComponentNameError,
    SqlAlchemyCodeRepoRepository,
    SqlAlchemyContextDataRepository,
    SqlAlchemySystemComponentRepository,
    SystemComponentRepository,
)
from app.schemas import (
    AgentContextRequest,
    AgentContextResponse,
    ApiContractCreate,
    ApiContractResponse,
    CodeRepoCreate,
    CodeRepoResponse,
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
    SystemComponentCreate,
    SystemComponentResponse,
)

app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_system_component_repository(
    db: Session = Depends(get_db),
) -> SystemComponentRepository:
    return SqlAlchemySystemComponentRepository(db)


def get_code_repo_repository(db: Session = Depends(get_db)):
    return SqlAlchemyCodeRepoRepository(db)


def get_context_data_repository(db: Session = Depends(get_db)):
    return SqlAlchemyContextDataRepository(db)


def get_system_component_service(
    repository: SystemComponentRepository = Depends(get_system_component_repository),
) -> SystemComponentService:
    return SystemComponentService(repository)


def get_code_repo_service(
    code_repo_repository=Depends(get_code_repo_repository),
    system_component_repository: SystemComponentRepository = Depends(
        get_system_component_repository
    ),
) -> CodeRepoService:
    return CodeRepoService(code_repo_repository, system_component_repository)


def get_context_service(context_repository=Depends(get_context_data_repository)) -> ContextService:
    return ContextService(context_repository)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/system-components", response_model=SystemComponentResponse)
def create_system_component(
    system_component: SystemComponentCreate,
    component_service: SystemComponentService = Depends(get_system_component_service),
):
    try:
        return component_service.create(
            name=system_component.name,
            description=system_component.description,
        )
    except DuplicateSystemComponentNameError as exc:
        raise HTTPException(
            status_code=409,
            detail="System component name already exists",
        ) from exc


@app.get("/system-components", response_model=list[SystemComponentResponse])
def list_system_components(
    component_service: SystemComponentService = Depends(get_system_component_service),
):
    return component_service.list()


@app.get("/system-components/{system_component_id}", response_model=SystemComponentResponse)
def get_system_component(
    system_component_id: UUID,
    component_service: SystemComponentService = Depends(get_system_component_service),
):
    try:
        return component_service.get_by_id(system_component_id)
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")


@app.post("/code-repos", response_model=CodeRepoResponse)
def create_code_repo(
    code_repo: CodeRepoCreate,
    code_repo_service: CodeRepoService = Depends(get_code_repo_service),
):
    try:
        return code_repo_service.create(
            system_component_id=code_repo.system_component_id,
            provider=code_repo.provider,
            name=code_repo.name,
            url=code_repo.url,
            default_branch=code_repo.default_branch,
        )
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")
    except DuplicateCodeRepoError:
        raise HTTPException(status_code=409, detail="Code repo already exists")


@app.get("/code-repos", response_model=list[CodeRepoResponse])
def list_code_repos(code_repo_service: CodeRepoService = Depends(get_code_repo_service)):
    return code_repo_service.list()


@app.get("/code-repos/{code_repo_id}", response_model=CodeRepoResponse)
def get_code_repo(
    code_repo_id: UUID,
    code_repo_service: CodeRepoService = Depends(get_code_repo_service),
):
    try:
        return code_repo_service.get_by_id(code_repo_id)
    except CodeRepoNotFoundError:
        raise HTTPException(status_code=404, detail="Code repo not found")


@app.get(
    "/system-components/{system_component_id}/code-repos",
    response_model=list[CodeRepoResponse],
)
def list_code_repos_by_system_component(
    system_component_id: UUID,
    code_repo_service: CodeRepoService = Depends(get_code_repo_service),
):
    try:
        return code_repo_service.list_by_system_component(system_component_id)
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")


@app.post("/pull-requests", response_model=PullRequestResponse)
def create_pull_request(
    payload: PullRequestCreate,
    context_repo=Depends(get_context_data_repository),
):
    return context_repo.create_pull_request(**payload.model_dump())


@app.get("/pull-requests", response_model=list[PullRequestResponse])
def list_pull_requests(context_repo=Depends(get_context_data_repository)):
    return context_repo.list_pull_requests()


@app.post("/commits", response_model=CommitResponse)
def create_commit(payload: CommitCreate, context_repo=Depends(get_context_data_repository)):
    data = payload.model_dump()
    if not data.get("committed_at"):
        data.pop("committed_at", None)
    return context_repo.create_commit(**data)


@app.get("/commits", response_model=list[CommitResponse])
def list_commits(context_repo=Depends(get_context_data_repository)):
    return context_repo.list_commits()


@app.post("/deployments", response_model=DeploymentResponse)
def create_deployment(
    payload: DeploymentCreate,
    context_repo=Depends(get_context_data_repository),
):
    data = payload.model_dump()
    if not data.get("deployed_at"):
        data.pop("deployed_at", None)
    return context_repo.create_deployment(**data)


@app.get("/deployments", response_model=list[DeploymentResponse])
def list_deployments(context_repo=Depends(get_context_data_repository)):
    return context_repo.list_deployments()


@app.post("/runtime-snapshots", response_model=RuntimeSnapshotResponse)
def create_runtime_snapshot(
    payload: RuntimeSnapshotCreate,
    context_repo=Depends(get_context_data_repository),
):
    data = payload.model_dump()
    if not data.get("captured_at"):
        data.pop("captured_at", None)
    return context_repo.create_runtime_snapshot(**data)


@app.get("/runtime-snapshots", response_model=list[RuntimeSnapshotResponse])
def list_runtime_snapshots(context_repo=Depends(get_context_data_repository)):
    return context_repo.list_runtime_snapshots()


@app.post("/api-contracts", response_model=ApiContractResponse)
def create_api_contract(
    payload: ApiContractCreate,
    context_repo=Depends(get_context_data_repository),
):
    data = payload.model_dump()
    if not data.get("captured_at"):
        data.pop("captured_at", None)
    return context_repo.create_api_contract(**data)


@app.get("/api-contracts", response_model=list[ApiContractResponse])
def list_api_contracts(context_repo=Depends(get_context_data_repository)):
    return context_repo.list_api_contracts()


@app.post("/endpoints", response_model=EndpointResponse)
def create_endpoint(payload: EndpointCreate, context_repo=Depends(get_context_data_repository)):
    return context_repo.create_endpoint(**payload.model_dump())


@app.get("/endpoints", response_model=list[EndpointResponse])
def list_endpoints(context_repo=Depends(get_context_data_repository)):
    return context_repo.list_endpoints()


@app.post("/dependencies", response_model=DependencyResponse)
def create_dependency(
    payload: DependencyCreate,
    context_repo=Depends(get_context_data_repository),
):
    data = payload.model_dump()
    if not data.get("captured_at"):
        data.pop("captured_at", None)
    return context_repo.create_dependency(**data)


@app.get("/dependencies", response_model=list[DependencyResponse])
def list_dependencies(context_repo=Depends(get_context_data_repository)):
    return context_repo.list_dependencies()


@app.post("/sync-runs", response_model=SyncRunResponse)
def create_sync_run(payload: SyncRunCreate, context_repo=Depends(get_context_data_repository)):
    data = payload.model_dump()
    if not data.get("started_at"):
        data.pop("started_at", None)
    return context_repo.create_sync_run(**data)


@app.get("/sync-runs", response_model=list[SyncRunResponse])
def list_sync_runs(context_repo=Depends(get_context_data_repository)):
    return context_repo.list_sync_runs()


@app.get("/context/system/current-state")
def get_system_current_state(context_repo=Depends(get_context_data_repository)):
    return {
        "system_component_count": context_repo.db.query(SystemComponent).count(),
        "code_repo_count": len(context_repo.list_code_repos()),
        "deployment_count": len(context_repo.list_deployments()),
        "runtime_snapshot_count": len(context_repo.list_runtime_snapshots()),
    }


@app.get("/context/system-component/{name}", response_model=AgentContextResponse)
def get_system_component_context(
    name: str,
    environment: str | None = None,
    context_service: ContextService = Depends(get_context_service),
):
    try:
        return context_service.get_system_component_context(name, environment)
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")


@app.get("/context/system-component/{name}/changes")
def get_system_component_changes(
    name: str,
    context_service: ContextService = Depends(get_context_service),
):
    try:
        context = context_service.get_system_component_context(name)
        return {
            "system_component": context["system_component"],
            "recent_pull_requests": context["recent_pull_requests"],
            "recent_commits": context["recent_commits"],
        }
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")


@app.get("/context/system-component/{name}/runtime")
def get_system_component_runtime(
    name: str,
    environment: str | None = None,
    context_service: ContextService = Depends(get_context_service),
):
    try:
        context = context_service.get_system_component_context(name, environment)
        return {
            "system_component": context["system_component"],
            "environment": context["environment"],
            "latest_runtime_health": context["latest_runtime_health"],
            "latest_deployment_version": context["latest_deployment_version"],
        }
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")


@app.get("/context/system-component/{name}/dependencies")
def get_system_component_dependencies(
    name: str,
    context_service: ContextService = Depends(get_context_service),
):
    try:
        context = context_service.get_system_component_context(name)
        return {
            "system_component": context["system_component"],
            "dependencies": context["dependencies"],
        }
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")


@app.post("/agent/context", response_model=AgentContextResponse)
def post_agent_context(
    payload: AgentContextRequest,
    context_service: ContextService = Depends(get_context_service),
):
    try:
        return context_service.get_system_component_context(
            payload.system_component_name,
            payload.environment,
        )
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")
