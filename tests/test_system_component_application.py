from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.application.system_component_service import (
    SystemComponentNotFoundError,
    SystemComponentService,
)
from app.models import SystemComponent
from app.repositories import DuplicateSystemComponentNameError


class FakeRepository:
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

    def get_by_id(self, system_component_id: UUID) -> SystemComponent | None:
        return self._items.get(system_component_id)


def test_create_and_list_system_components() -> None:
    repo = FakeRepository()
    service = SystemComponentService(repo)

    created = service.create(name="payment-api", description="Handles payments")
    assert created.name == "payment-api"

    listed = service.list()
    assert len(listed) == 1
    assert listed[0].name == "payment-api"


def test_get_by_id_raises_not_found() -> None:
    repo = FakeRepository()
    service = SystemComponentService(repo)

    try:
        service.get_by_id(uuid4())
        assert False, "Expected SystemComponentNotFoundError"
    except SystemComponentNotFoundError:
        assert True
