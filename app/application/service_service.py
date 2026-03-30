from uuid import UUID

from app.repositories import ServiceRepository


class ServiceNotFoundError(Exception):
    pass


class Service:
    def __init__(self, repository: ServiceRepository) -> None:
        self.repository = repository

    def create(self, name: str, description: str | None = None):
        return self.repository.create(name=name, description=description)

    def list(self):
        return self.repository.list()

    def get_by_id(self, service_id: UUID):
        service = self.repository.get_by_id(service_id)
        if not service:
            raise ServiceNotFoundError
        return service
