from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.application.service_service import Service, ServiceNotFoundError
from app.models import Service as ServiceModel
from app.repositories import DuplicateServiceNameError


class FakeRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, ServiceModel] = {}

    def create(self, name: str, description: str | None = None) -> ServiceModel:
        if any(item.name == name for item in self._items.values()):
            raise DuplicateServiceNameError
        now = datetime.now(timezone.utc)
        service = ServiceModel(
            id=uuid4(),
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self._items[service.id] = service
        return service

    def list(self) -> list[ServiceModel]:
        return list(self._items.values())

    def get_by_id(self, service_id: UUID) -> ServiceModel | None:
        return self._items.get(service_id)


def test_create_and_list_services() -> None:
    repo = FakeRepository()
    service = Service(repo)

    created = service.create(name="payment-api", description="Handles payments")
    assert created.name == "payment-api"

    listed = service.list()
    assert len(listed) == 1
    assert listed[0].name == "payment-api"


def test_get_by_id_raises_not_found() -> None:
    repo = FakeRepository()
    service = Service(repo)

    try:
        service.get_by_id(uuid4())
        assert False, "Expected ServiceNotFoundError"
    except ServiceNotFoundError:
        assert True
