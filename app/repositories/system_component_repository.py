from typing import List, Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CodeRepo, SystemComponent


class DuplicateSystemComponentNameError(Exception):
    pass


class DuplicateCodeRepoError(Exception):
    pass


class SystemComponentRepository(Protocol):
    def create(self, name: str, description: str | None = None) -> SystemComponent: ...

    def list(self) -> List[SystemComponent]: ...

    def get_by_id(self, system_component_id: UUID) -> SystemComponent | None: ...


class CodeRepoRepository(Protocol):
    def create(
        self,
        system_component_id: UUID,
        provider: str,
        name: str,
        url: str,
        default_branch: str | None = None,
    ) -> CodeRepo: ...

    def list(self) -> List[CodeRepo]: ...

    def get_by_id(self, code_repo_id: UUID) -> CodeRepo | None: ...

    def list_by_system_component(self, system_component_id: UUID) -> List[CodeRepo]: ...


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

    def list(self) -> List[SystemComponent]:
        return self.db.query(SystemComponent).all()

    def get_by_id(self, system_component_id: UUID) -> SystemComponent | None:
        return (
            self.db.query(SystemComponent)
            .filter(SystemComponent.id == system_component_id)
            .first()
        )


class SqlAlchemyCodeRepoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        system_component_id: UUID,
        provider: str,
        name: str,
        url: str,
        default_branch: str | None = None,
    ) -> CodeRepo:
        code_repo = CodeRepo(
            system_component_id=system_component_id,
            provider=provider,
            name=name,
            url=url,
            default_branch=default_branch,
        )
        try:
            self.db.add(code_repo)
            self.db.commit()
            self.db.refresh(code_repo)
            return code_repo
        except IntegrityError as exc:
            self.db.rollback()
            orig = exc.orig
            pgcode = getattr(orig, "pgcode", None)
            constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
            message = str(orig)
            is_unique_violation = (
                pgcode == "23505"
                or constraint == "code_repo_provider_name_key"
                or "code_repo_provider_name_key" in message
                or "UNIQUE constraint failed" in message
            )
            if is_unique_violation:
                raise DuplicateCodeRepoError from exc
            raise

    def list(self) -> List[CodeRepo]:
        return self.db.query(CodeRepo).all()

    def get_by_id(self, code_repo_id: UUID) -> CodeRepo | None:
        return self.db.query(CodeRepo).filter(CodeRepo.id == code_repo_id).first()

    def list_by_system_component(self, system_component_id: UUID) -> List[CodeRepo]:
        return (
            self.db.query(CodeRepo)
            .filter(CodeRepo.system_component_id == system_component_id)
            .all()
        )
