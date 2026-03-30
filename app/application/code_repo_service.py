from uuid import UUID

from app.application.system_component_service import SystemComponentNotFoundError
from app.repositories import CodeRepoRepository, SystemComponentRepository


class CodeRepoNotFoundError(Exception):
    pass


class CodeRepoService:
    def __init__(
        self,
        code_repo_repository: CodeRepoRepository,
        system_component_repository: SystemComponentRepository,
    ) -> None:
        self.code_repo_repository = code_repo_repository
        self.system_component_repository = system_component_repository

    def create(
        self,
        system_component_id: UUID,
        provider: str,
        name: str,
        url: str,
        default_branch: str | None = None,
    ):
        if not self.system_component_repository.get_by_id(system_component_id):
            raise SystemComponentNotFoundError

        return self.code_repo_repository.create(
            system_component_id=system_component_id,
            provider=provider,
            name=name,
            url=url,
            default_branch=default_branch,
        )

    def list(self):
        return self.code_repo_repository.list()

    def get_by_id(self, code_repo_id: UUID):
        code_repo = self.code_repo_repository.get_by_id(code_repo_id)
        if not code_repo:
            raise CodeRepoNotFoundError
        return code_repo

    def list_by_system_component(self, system_component_id: UUID):
        if not self.system_component_repository.get_by_id(system_component_id):
            raise SystemComponentNotFoundError
        return self.code_repo_repository.list_by_system_component(system_component_id)
