from typing import Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Service


class DuplicateServiceNameError(Exception):
    pass


class ServiceRepository(Protocol):
    def create(self, name: str, description: str | None = None) -> Service: ...

    def list(self) -> list[Service]: ...

    def get_by_id(self, service_id: UUID) -> Service | None: ...


class SqlAlchemyServiceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str, description: str | None = None) -> Service:
        service = Service(name=name, description=description)
        try:
            self.db.add(service)
            self.db.commit()
            self.db.refresh(service)
            return service
        except IntegrityError as exc:
            self.db.rollback()
            orig = exc.orig
            pgcode = getattr(orig, "pgcode", None)
            constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
            message = str(orig)
            is_unique_violation = (
                pgcode == "23505"
                or constraint == "service_name_key"
                or "service_name_key" in message
                or "UNIQUE constraint failed" in message
            )
            if is_unique_violation:
                raise DuplicateServiceNameError from exc
            raise

    def list(self) -> list[Service]:
        return self.db.query(Service).all()

    def get_by_id(self, service_id: UUID) -> Service | None:
        return self.db.query(Service).filter(Service.id == service_id).first()
