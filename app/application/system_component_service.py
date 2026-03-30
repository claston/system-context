from uuid import UUID

from app.repositories import SystemComponentRepository


class SystemComponentNotFoundError(Exception):
    pass


class SystemComponentService:
    def __init__(self, repository: SystemComponentRepository) -> None:
        self.repository = repository

    def create(self, name: str, description: str | None = None):
        return self.repository.create(name=name, description=description)

    def list(self):
        return self.repository.list()

    def get_by_id(self, system_component_id: UUID):
        system_component = self.repository.get_by_id(system_component_id)
        if not system_component:
            raise SystemComponentNotFoundError
        return system_component
