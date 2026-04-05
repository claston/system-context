from uuid import UUID

from app.application.system_component_service import SystemComponentNotFoundError
from app.repositories import (
    IntegrationTargetMappingNotFoundError,
    IntegrationTargetMappingRepository,
    SystemComponentRepository,
)


class IntegrationTargetMappingService:
    def __init__(
        self,
        mapping_repository: IntegrationTargetMappingRepository,
        system_component_repository: SystemComponentRepository,
    ) -> None:
        self.mapping_repository = mapping_repository
        self.system_component_repository = system_component_repository

    def create(
        self,
        *,
        connector_name: str,
        external_target_id: str,
        system_component_id: UUID,
        external_target_name: str | None = None,
        environment: str = "",
        metadata_json: dict | None = None,
        is_active: bool = True,
    ):
        if not self.system_component_repository.get_by_id(system_component_id):
            raise SystemComponentNotFoundError
        return self.mapping_repository.create(
            connector_name=connector_name,
            external_target_id=external_target_id,
            system_component_id=system_component_id,
            external_target_name=external_target_name,
            environment=environment,
            metadata_json=metadata_json,
            is_active=is_active,
        )

    def list(
        self,
        *,
        connector_name: str | None = None,
        environment: str | None = None,
        system_component_id: UUID | None = None,
        is_active: bool | None = None,
    ):
        return self.mapping_repository.list(
            connector_name=connector_name,
            environment=environment,
            system_component_id=system_component_id,
            is_active=is_active,
        )

    def get_by_id(self, mapping_id: UUID):
        item = self.mapping_repository.get_by_id(mapping_id)
        if item is None:
            raise IntegrationTargetMappingNotFoundError
        return item

    def update(self, mapping_id: UUID, **kwargs):
        system_component_id = kwargs.get("system_component_id")
        if system_component_id is not None and not self.system_component_repository.get_by_id(
            system_component_id
        ):
            raise SystemComponentNotFoundError
        return self.mapping_repository.update(mapping_id, **kwargs)
