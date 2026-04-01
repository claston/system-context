from typing import List, Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ApiContract,
    CodeRepo,
    Commit,
    Dependency,
    Deployment,
    Endpoint,
    PullRequest,
    RuntimeSnapshot,
    SyncRun,
    SystemComponent,
)


class DuplicateSystemComponentNameError(Exception):
    pass


class DuplicateCodeRepoError(Exception):
    pass


class DuplicateContextEntityError(Exception):
    pass


class ContextEntityReferenceNotFoundError(Exception):
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


class ContextDataRepository(Protocol):
    def list_code_repos(self) -> List[CodeRepo]: ...

    def create_pull_request(self, **kwargs) -> PullRequest: ...

    def list_pull_requests(self) -> List[PullRequest]: ...

    def create_commit(self, **kwargs) -> Commit: ...

    def list_commits(self) -> List[Commit]: ...

    def create_deployment(self, **kwargs) -> Deployment: ...

    def list_deployments(self) -> List[Deployment]: ...

    def create_runtime_snapshot(self, **kwargs) -> RuntimeSnapshot: ...

    def list_runtime_snapshots(self) -> List[RuntimeSnapshot]: ...

    def create_api_contract(self, **kwargs) -> ApiContract: ...

    def list_api_contracts(self) -> List[ApiContract]: ...

    def create_endpoint(self, **kwargs) -> Endpoint: ...

    def list_endpoints(self) -> List[Endpoint]: ...

    def create_dependency(self, **kwargs) -> Dependency: ...

    def list_dependencies(self) -> List[Dependency]: ...

    def create_sync_run(self, **kwargs) -> SyncRun: ...

    def list_sync_runs(self) -> List[SyncRun]: ...

    def get_sync_run_by_id(self, sync_run_id: UUID) -> SyncRun | None: ...

    def update_sync_run(self, sync_run_id: UUID, **kwargs) -> SyncRun: ...


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


class SqlAlchemyContextDataRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _create(self, model_class, **kwargs):
        instance = model_class(**kwargs)
        try:
            self.db.add(instance)
            self.db.commit()
            self.db.refresh(instance)
            return instance
        except IntegrityError as exc:
            self.db.rollback()
            orig = exc.orig
            pgcode = getattr(orig, "pgcode", None)
            message = str(orig)
            is_unique_violation = pgcode == "23505" or "UNIQUE constraint failed" in message
            is_foreign_key_violation = (
                pgcode == "23503" or "FOREIGN KEY constraint failed" in message
            )
            if is_unique_violation:
                raise DuplicateContextEntityError from exc
            if is_foreign_key_violation:
                raise ContextEntityReferenceNotFoundError from exc
            raise

    def list_code_repos(self) -> List[CodeRepo]:
        return self.db.query(CodeRepo).all()

    def create_pull_request(self, **kwargs) -> PullRequest:
        return self._create(PullRequest, **kwargs)

    def list_pull_requests(self) -> List[PullRequest]:
        return self.db.query(PullRequest).all()

    def create_commit(self, **kwargs) -> Commit:
        return self._create(Commit, **kwargs)

    def list_commits(self) -> List[Commit]:
        return self.db.query(Commit).all()

    def create_deployment(self, **kwargs) -> Deployment:
        return self._create(Deployment, **kwargs)

    def list_deployments(self) -> List[Deployment]:
        return self.db.query(Deployment).all()

    def create_runtime_snapshot(self, **kwargs) -> RuntimeSnapshot:
        return self._create(RuntimeSnapshot, **kwargs)

    def list_runtime_snapshots(self) -> List[RuntimeSnapshot]:
        return self.db.query(RuntimeSnapshot).all()

    def create_api_contract(self, **kwargs) -> ApiContract:
        return self._create(ApiContract, **kwargs)

    def list_api_contracts(self) -> List[ApiContract]:
        return self.db.query(ApiContract).all()

    def create_endpoint(self, **kwargs) -> Endpoint:
        return self._create(Endpoint, **kwargs)

    def list_endpoints(self) -> List[Endpoint]:
        return self.db.query(Endpoint).all()

    def create_dependency(self, **kwargs) -> Dependency:
        return self._create(Dependency, **kwargs)

    def list_dependencies(self) -> List[Dependency]:
        return self.db.query(Dependency).all()

    def create_sync_run(self, **kwargs) -> SyncRun:
        return self._create(SyncRun, **kwargs)

    def list_sync_runs(self) -> List[SyncRun]:
        return self.db.query(SyncRun).all()

    def get_sync_run_by_id(self, sync_run_id: UUID) -> SyncRun | None:
        return self.db.query(SyncRun).filter(SyncRun.id == sync_run_id).first()

    def update_sync_run(self, sync_run_id: UUID, **kwargs) -> SyncRun:
        item = self.get_sync_run_by_id(sync_run_id)
        if item is None:
            raise ContextEntityReferenceNotFoundError
        for key, value in kwargs.items():
            setattr(item, key, value)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_system_component_by_name(self, system_component_name: str) -> SystemComponent | None:
        return (
            self.db.query(SystemComponent)
            .filter(SystemComponent.name == system_component_name)
            .first()
        )

    def get_latest_deployment_for_system_component(
        self, system_component_id: UUID, environment: str | None = None
    ) -> Deployment | None:
        query = self.db.query(Deployment).filter(
            Deployment.system_component_id == system_component_id
        )
        if environment:
            query = query.filter(Deployment.environment == environment)
        return query.order_by(Deployment.deployed_at.desc()).first()

    def get_latest_runtime_for_system_component(
        self, system_component_id: UUID, environment: str | None = None
    ) -> RuntimeSnapshot | None:
        query = self.db.query(RuntimeSnapshot).filter(
            RuntimeSnapshot.system_component_id == system_component_id
        )
        if environment:
            query = query.filter(RuntimeSnapshot.environment == environment)
        return query.order_by(RuntimeSnapshot.captured_at.desc()).first()

    def get_recent_pull_requests_count_for_system_component(
        self, system_component_id: UUID
    ) -> int:
        return (
            self.db.query(PullRequest)
            .join(CodeRepo, PullRequest.code_repo_id == CodeRepo.id)
            .filter(CodeRepo.system_component_id == system_component_id)
            .count()
        )

    def get_recent_commits_count_for_system_component(self, system_component_id: UUID) -> int:
        return (
            self.db.query(Commit)
            .join(CodeRepo, Commit.code_repo_id == CodeRepo.id)
            .filter(CodeRepo.system_component_id == system_component_id)
            .count()
        )

    def get_dependencies_for_system_component(self, system_component_id: UUID) -> List[Dependency]:
        return (
            self.db.query(Dependency)
            .filter(Dependency.source_system_component_id == system_component_id)
            .all()
        )
