from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.application import (
    CodeRepoNotFoundError,
    CodeRepoService,
    SystemComponentNotFoundError,
)
from app.dependencies import get_code_repo_service
from app.repositories import DuplicateCodeRepoError
from app.schemas import CodeRepoCreate, CodeRepoResponse

router = APIRouter()


@router.post("/code-repos", response_model=CodeRepoResponse)
def create_code_repo(
    code_repo: CodeRepoCreate,
    code_repo_service: CodeRepoService = Depends(get_code_repo_service),
):
    try:
        return code_repo_service.create(
            system_component_id=code_repo.system_component_id,
            provider=code_repo.provider,
            name=code_repo.name,
            url=str(code_repo.url),
            default_branch=code_repo.default_branch,
        )
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")
    except DuplicateCodeRepoError:
        raise HTTPException(status_code=409, detail="Code repo already exists")


@router.get("/code-repos", response_model=list[CodeRepoResponse])
def list_code_repos(code_repo_service: CodeRepoService = Depends(get_code_repo_service)):
    return code_repo_service.list()


@router.get("/code-repos/{code_repo_id}", response_model=CodeRepoResponse)
def get_code_repo(
    code_repo_id: UUID,
    code_repo_service: CodeRepoService = Depends(get_code_repo_service),
):
    try:
        return code_repo_service.get_by_id(code_repo_id)
    except CodeRepoNotFoundError:
        raise HTTPException(status_code=404, detail="Code repo not found")


@router.get(
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
