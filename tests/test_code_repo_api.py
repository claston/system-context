from datetime import datetime, timezone
from typing import List
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.application import CodeRepoNotFoundError, SystemComponentNotFoundError
from app.main import app, get_code_repo_service
from app.models import CodeRepo
from app.repositories import DuplicateCodeRepoError


class FakeCodeRepoService:
    def __init__(self) -> None:
        self._items: dict[UUID, CodeRepo] = {}
        self._system_components: set[UUID] = {uuid4()}

    @property
    def valid_system_component_id(self) -> UUID:
        return next(iter(self._system_components))

    def create(
        self,
        system_component_id: UUID,
        provider: str,
        name: str,
        url: str,
        default_branch: str | None = None,
    ) -> CodeRepo:
        if system_component_id not in self._system_components:
            raise SystemComponentNotFoundError
        if any(item.provider == provider and item.name == name for item in self._items.values()):
            raise DuplicateCodeRepoError
        now = datetime.now(timezone.utc)
        code_repo = CodeRepo(
            id=uuid4(),
            system_component_id=system_component_id,
            provider=provider,
            name=name,
            url=url,
            default_branch=default_branch,
            created_at=now,
            updated_at=now,
        )
        self._items[code_repo.id] = code_repo
        return code_repo

    def list(self) -> List[CodeRepo]:
        return list(self._items.values())

    def get_by_id(self, code_repo_id: UUID) -> CodeRepo:
        code_repo = self._items.get(code_repo_id)
        if not code_repo:
            raise CodeRepoNotFoundError
        return code_repo

    def list_by_system_component(self, system_component_id: UUID) -> List[CodeRepo]:
        if system_component_id not in self._system_components:
            raise SystemComponentNotFoundError
        return [
            item
            for item in self._items.values()
            if item.system_component_id == system_component_id
        ]


def build_client(service: FakeCodeRepoService) -> TestClient:
    app.dependency_overrides[get_code_repo_service] = lambda: service
    return TestClient(app)


def test_create_code_repo() -> None:
    service = FakeCodeRepoService()
    client = build_client(service)

    response = client.post(
        "/code-repos",
        json={
            "system_component_id": str(service.valid_system_component_id),
            "provider": "github",
            "name": "payment-api",
            "url": "https://github.com/org/payment-api",
            "default_branch": "main",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "payment-api"
    app.dependency_overrides.clear()


def test_create_code_repo_invalid_system_component_returns_404() -> None:
    service = FakeCodeRepoService()
    client = build_client(service)

    response = client.post(
        "/code-repos",
        json={
            "system_component_id": str(uuid4()),
            "provider": "github",
            "name": "payment-api",
            "url": "https://github.com/org/payment-api",
            "default_branch": "main",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "System component not found"
    app.dependency_overrides.clear()


def test_list_and_get_code_repo() -> None:
    service = FakeCodeRepoService()
    created = service.create(
        system_component_id=service.valid_system_component_id,
        provider="github",
        name="payment-api",
        url="https://github.com/org/payment-api",
        default_branch="main",
    )
    client = build_client(service)

    listed = client.get("/code-repos")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/code-repos/{created.id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == str(created.id)

    missing = client.get(f"/code-repos/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Code repo not found"
    app.dependency_overrides.clear()


def test_list_by_system_component() -> None:
    service = FakeCodeRepoService()
    created = service.create(
        system_component_id=service.valid_system_component_id,
        provider="github",
        name="payment-api",
        url="https://github.com/org/payment-api",
        default_branch="main",
    )
    client = build_client(service)

    response = client.get(f"/system-components/{service.valid_system_component_id}/code-repos")
    assert response.status_code == 200
    assert response.json()[0]["id"] == str(created.id)
    app.dependency_overrides.clear()
