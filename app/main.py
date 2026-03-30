from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.application import (
    CodeRepoNotFoundError,
    CodeRepoService,
    SystemComponentNotFoundError,
    SystemComponentService,
)
from app.db import SessionLocal
from app.repositories import (
    DuplicateCodeRepoError,
    DuplicateSystemComponentNameError,
    SqlAlchemyCodeRepoRepository,
    SqlAlchemySystemComponentRepository,
    SystemComponentRepository,
)
from app.schemas import (
    CodeRepoCreate,
    CodeRepoResponse,
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
