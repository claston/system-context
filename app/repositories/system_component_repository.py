from typing import Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import SystemComponent


class DuplicateSystemComponentNameError(Exception):
    pass


class SystemComponentRepository(Protocol):
    def create(self, name: str, description: str | None = None) -> SystemComponent: ...

    def list(self) -> list[SystemComponent]: ...

    def get_by_id(self, system_component_id: UUID) -> SystemComponent | None: ...


class SqlAlchemySystemComponentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str, description: str | None = None) -> SystemComponent:
        system_component = SystemComponent(name=name, description=description)
        try:
            self.db.add(system_component)
            self.db.commit()
            self.db.refresh(system_component)
            return system_component
        except IntegrityError as exc:
            self.db.rollback()
            orig = exc.orig
            pgcode = getattr(orig, "pgcode", None)
            constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
            message = str(orig)
            is_unique_violation = (
                pgcode == "23505"
                or constraint in {"system_component_name_key", "service_name_key"}
                or "system_component_name_key" in message
                or "service_name_key" in message
                or "UNIQUE constraint failed" in message
            )
            if is_unique_violation:
                raise DuplicateSystemComponentNameError from exc
            raise

    def list(self) -> list[SystemComponent]:
        return self.db.query(SystemComponent).all()

    def get_by_id(self, system_component_id: UUID) -> SystemComponent | None:
        return (
            self.db.query(SystemComponent)
            .filter(SystemComponent.id == system_component_id)
            .first()
        )
