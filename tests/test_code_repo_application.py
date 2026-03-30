from typing import List
from uuid import UUID, uuid4

from app.application import CodeRepoNotFoundError, CodeRepoService, SystemComponentNotFoundError
from app.models import CodeRepo, SystemComponent
from app.repositories import DuplicateCodeRepoError


class FakeSystemComponentRepository:
    def __init__(self, existing_ids: set[UUID] | None = None) -> None:
        self._ids = existing_ids or set()

    def get_by_id(self, system_component_id: UUID) -> SystemComponent | None:
        if system_component_id in self._ids:
            sc = SystemComponent(id=system_component_id, name="a", description=None)
            return sc
        return None


class FakeCodeRepoRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, CodeRepo] = {}

    def create(
        self,
        system_component_id: UUID,
        provider: str,
        name: str,
        url: str,
        default_branch: str | None = None,
    ) -> CodeRepo:
        if any(item.provider == provider and item.name == name for item in self._items.values()):
            raise DuplicateCodeRepoError
        repo = CodeRepo(
            id=uuid4(),
            system_component_id=system_component_id,
            provider=provider,
            name=name,
            url=url,
            default_branch=default_branch,
        )
        self._items[repo.id] = repo
        return repo

    def list(self) -> List[CodeRepo]:
        return list(self._items.values())

    def get_by_id(self, code_repo_id: UUID) -> CodeRepo | None:
        return self._items.get(code_repo_id)

    def list_by_system_component(self, system_component_id: UUID) -> List[CodeRepo]:
        return [
            item
            for item in self._items.values()
            if item.system_component_id == system_component_id
        ]


def test_create_code_repo_and_list() -> None:
    system_component_id = uuid4()
    service = CodeRepoService(
        code_repo_repository=FakeCodeRepoRepository(),
        system_component_repository=FakeSystemComponentRepository({system_component_id}),
    )

    created = service.create(
        system_component_id=system_component_id,
        provider="github",
        name="payment-api",
        url="https://github.com/org/payment-api",
        default_branch="main",
    )
    assert created.name == "payment-api"

    listed = service.list()
    assert len(listed) == 1


def test_create_code_repo_with_missing_system_component_raises_not_found() -> None:
    service = CodeRepoService(
        code_repo_repository=FakeCodeRepoRepository(),
        system_component_repository=FakeSystemComponentRepository(set()),
    )

    try:
        service.create(
            system_component_id=uuid4(),
            provider="github",
            name="payment-api",
            url="https://github.com/org/payment-api",
            default_branch="main",
        )
        assert False, "Expected SystemComponentNotFoundError"
    except SystemComponentNotFoundError:
        assert True


def test_get_code_repo_by_id_raises_not_found() -> None:
    service = CodeRepoService(
        code_repo_repository=FakeCodeRepoRepository(),
        system_component_repository=FakeSystemComponentRepository(set()),
    )
    try:
        service.get_by_id(uuid4())
        assert False, "Expected CodeRepoNotFoundError"
    except CodeRepoNotFoundError:
        assert True
