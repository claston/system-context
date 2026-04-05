from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.application import SystemComponentNotFoundError
from app.main import app, get_system_component_service
from app.models import SystemComponent
from app.repositories import DuplicateSystemComponentNameError


class FakeSystemComponentService:
    def __init__(self) -> None:
        self._items: dict[UUID, SystemComponent] = {}

    def create(self, name: str, description: str | None = None) -> SystemComponent:
        if any(item.name == name for item in self._items.values()):
            raise DuplicateSystemComponentNameError
        now = datetime.now(timezone.utc)
        system_component = SystemComponent(
            id=uuid4(),
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self._items[system_component.id] = system_component
        return system_component

    def list(self) -> list[SystemComponent]:
        return list(self._items.values())

    def get_by_id(self, system_component_id: UUID) -> SystemComponent:
        system_component = self._items.get(system_component_id)
        if not system_component:
            raise SystemComponentNotFoundError
        return system_component


def build_client(service: FakeSystemComponentService) -> TestClient:
    app.dependency_overrides[get_system_component_service] = lambda: service
    return TestClient(app)


def test_create_system_component() -> None:
    service = FakeSystemComponentService()
    client = build_client(service)

    response = client.post(
        "/system-components",
        json={"name": "payment-api", "description": "Handles payments"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "payment-api"
    assert data["description"] == "Handles payments"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    app.dependency_overrides.clear()


def test_list_system_components() -> None:
    service = FakeSystemComponentService()
    service.create(name="payment-api", description="A")
    service.create(name="ledger-api", description="B")
    client = build_client(service)

    response = client.get("/system-components")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {item["name"] for item in data} == {"payment-api", "ledger-api"}
    app.dependency_overrides.clear()


def test_get_system_component_by_id_and_not_found() -> None:
    service = FakeSystemComponentService()
    created = service.create(name="payment-api", description="A")
    client = build_client(service)

    found = client.get(f"/system-components/{created.id}")
    assert found.status_code == 200
    assert found.json()["id"] == str(created.id)

    missing = client.get(f"/system-components/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "System component not found"
    app.dependency_overrides.clear()


def test_create_system_component_duplicate_name_returns_409() -> None:
    service = FakeSystemComponentService()
    client = build_client(service)

    first = client.post(
        "/system-components",
        json={"name": "payment-api", "description": "Handles payments"},
    )
    assert first.status_code == 200

    second = client.post(
        "/system-components",
        json={"name": "payment-api", "description": "Duplicate"},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "System component name already exists"
    app.dependency_overrides.clear()


def test_release_check_returns_default_release_when_env_not_set(monkeypatch) -> None:
    monkeypatch.delenv("APP_RELEASE", raising=False)
    client = TestClient(app)

    response = client.get("/release-check")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "release": "v0.1.1-render-sync"}


def test_release_check_returns_app_release_from_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_RELEASE", "v2026.04.05-render-test-1")
    client = TestClient(app)

    response = client.get("/release-check")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "release": "v2026.04.05-render-test-1"}
