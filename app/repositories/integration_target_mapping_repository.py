from dataclasses import dataclass
from typing import List, Protocol
from uuid import UUID

from sqlalchemy import case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IntegrationTargetMapping, SystemComponent


class DuplicateIntegrationTargetMappingError(Exception):
    pass


class IntegrationTargetMappingNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ConnectorTargetComponentMapping:
    external_target_id: str
    system_component_name: str


class IntegrationTargetMappingRepository(Protocol):
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
    ) -> IntegrationTargetMapping: ...

    def list(
        self,
        *,
        connector_name: str | None = None,
        environment: str | None = None,
        system_component_id: UUID | None = None,
        is_active: bool | None = None,
    ) -> List[IntegrationTargetMapping]: ...

    def get_by_id(self, mapping_id: UUID) -> IntegrationTargetMapping | None: ...

    def update(
        self,
        mapping_id: UUID,
        **kwargs,
    ) -> IntegrationTargetMapping: ...

    def list_active_target_component_mappings(
        self, connector_name: str, environment: str | None = None
    ) -> List[ConnectorTargetComponentMapping]: ...


class SqlAlchemyIntegrationTargetMappingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _normalize_required_text(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    def _normalize_environment(self, value: str | None) -> str:
        return (value or "").strip()

    def _save(self, mapping: IntegrationTargetMapping) -> IntegrationTargetMapping:
        try:
            self.db.add(mapping)
            self.db.commit()
            self.db.refresh(mapping)
            return mapping
        except IntegrityError as exc:
            self.db.rollback()
            orig = exc.orig
            pgcode = getattr(orig, "pgcode", None)
            constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
            message = str(orig)
            is_unique_violation = (
                pgcode == "23505"
                or constraint
                == "integration_target_mapping_connector_target_environment_key"
                or "integration_target_mapping_connector_target_environment_key"
                in message
                or "UNIQUE constraint failed" in message
            )
            if is_unique_violation:
                raise DuplicateIntegrationTargetMappingError from exc
            raise

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
    ) -> IntegrationTargetMapping:
        normalized_external_target_name = None
        if external_target_name is not None:
            normalized_external_target_name = external_target_name.strip() or None
        mapping = IntegrationTargetMapping(
            connector_name=self._normalize_required_text(connector_name),
            external_target_id=self._normalize_required_text(external_target_id),
            system_component_id=system_component_id,
            external_target_name=normalized_external_target_name,
            environment=self._normalize_environment(environment),
            metadata_json=metadata_json,
            is_active=is_active,
        )
        return self._save(mapping)

    def list(
        self,
        *,
        connector_name: str | None = None,
        environment: str | None = None,
        system_component_id: UUID | None = None,
        is_active: bool | None = None,
    ) -> List[IntegrationTargetMapping]:
        query = self.db.query(IntegrationTargetMapping)
        if connector_name is not None:
            normalized_connector_name = connector_name.strip()
            if normalized_connector_name:
                query = query.filter(
                    IntegrationTargetMapping.connector_name
                    == normalized_connector_name
                )
        if environment is not None:
            query = query.filter(
                IntegrationTargetMapping.environment == self._normalize_environment(environment)
            )
        if system_component_id is not None:
            query = query.filter(
                IntegrationTargetMapping.system_component_id == system_component_id
            )
        if is_active is not None:
            query = query.filter(IntegrationTargetMapping.is_active.is_(is_active))
        return query.order_by(IntegrationTargetMapping.created_at.asc()).all()

    def get_by_id(self, mapping_id: UUID) -> IntegrationTargetMapping | None:
        return (
            self.db.query(IntegrationTargetMapping)
            .filter(IntegrationTargetMapping.id == mapping_id)
            .first()
        )

    def update(
        self,
        mapping_id: UUID,
        **kwargs,
    ) -> IntegrationTargetMapping:
        mapping = self.get_by_id(mapping_id)
        if mapping is None:
            raise IntegrationTargetMappingNotFoundError

        if "connector_name" in kwargs:
            kwargs["connector_name"] = self._normalize_required_text(
                kwargs["connector_name"]
            )
        if "external_target_id" in kwargs:
            kwargs["external_target_id"] = self._normalize_required_text(
                kwargs["external_target_id"]
            )
        if "external_target_name" in kwargs:
            value = kwargs["external_target_name"]
            kwargs["external_target_name"] = (
                None if value is None else (value.strip() or None)
            )
        if "environment" in kwargs:
            kwargs["environment"] = self._normalize_environment(kwargs["environment"])

        for key, value in kwargs.items():
            setattr(mapping, key, value)
        return self._save(mapping)

    def list_active_target_component_mappings(
        self, connector_name: str, environment: str | None = None
    ) -> List[ConnectorTargetComponentMapping]:
        normalized_environment = (environment or "").strip()

        query = (
            self.db.query(
                IntegrationTargetMapping.external_target_id,
                SystemComponent.name,
                IntegrationTargetMapping.environment,
            )
            .join(
                SystemComponent,
                SystemComponent.id == IntegrationTargetMapping.system_component_id,
            )
            .filter(
                IntegrationTargetMapping.connector_name == connector_name,
                IntegrationTargetMapping.is_active.is_(True),
            )
        )
        if normalized_environment:
            query = query.filter(
                IntegrationTargetMapping.environment.in_(
                    [normalized_environment, ""]
                )
            )
            query = query.order_by(
                case(
                    (
                        IntegrationTargetMapping.environment
                        == normalized_environment,
                        0,
                    ),
                    else_=1,
                ),
                IntegrationTargetMapping.created_at.asc(),
            )
        else:
            query = query.order_by(IntegrationTargetMapping.created_at.asc())

        rows = query.all()
        deduped_by_target: dict[str, ConnectorTargetComponentMapping] = {}
        for external_target_id, system_component_name, _ in rows:
            if external_target_id in deduped_by_target:
                continue
            deduped_by_target[external_target_id] = ConnectorTargetComponentMapping(
                external_target_id=external_target_id,
                system_component_name=system_component_name,
            )
        return list(deduped_by_target.values())
