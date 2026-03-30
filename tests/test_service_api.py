from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.application import ServiceNotFoundError
from app.main import app, get_service_service
from app.models import Service
from app.repositories import DuplicateServiceNameError


class FakeService:
    def __init__(self) -> None:
        self._items: dict[UUID, Service] = {}

    def create(self, name: str, description: str | None = None) -> Service:
        if any(item.name == name for item in self._items.values()):
            raise DuplicateServiceNameError
        now = datetime.now(timezone.utc)
        service = Service(
            id=uuid4(),
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self._items[service.id] = service
        return service

    def list(self) -> list[Service]:
        return list(self._items.values())

    def get_by_id(self, service_id: UUID) -> Service:
        service = self._items.get(service_id)
        if not service:
            raise ServiceNotFoundError
        return service


def build_client(service: FakeService) -> TestClient:
    app.dependency_overrides[get_service_service] = lambda: service
    return TestClient(app)


def test_create_service() -> None:
    service = FakeService()
    client = build_client(service)

    response = client.post(
        "/services",
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


def test_list_services() -> None:
    service = FakeService()
    service.create(name="payment-api", description="A")
    service.create(name="ledger-api", description="B")
    client = build_client(service)

    response = client.get("/services")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {item["name"] for item in data} == {"payment-api", "ledger-api"}
    app.dependency_overrides.clear()


def test_get_service_by_id_and_not_found() -> None:
    service = FakeService()
    created = service.create(name="payment-api", description="A")
    client = build_client(service)

    found = client.get(f"/services/{created.id}")
    assert found.status_code == 200
    assert found.json()["id"] == str(created.id)

    missing = client.get(f"/services/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Service not found"
    app.dependency_overrides.clear()


def test_create_service_duplicate_name_returns_409() -> None:
    service = FakeService()
    client = build_client(service)

    first = client.post(
        "/services",
        json={"name": "payment-api", "description": "Handles payments"},
    )
    assert first.status_code == 200

    second = client.post(
        "/services",
        json={"name": "payment-api", "description": "Duplicate"},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Service name already exists"
    app.dependency_overrides.clear()
