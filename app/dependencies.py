from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application import (
    CodeRepoService,
    ContextService,
    SyncJobDispatcher,
    SyncService,
    SystemComponentService,
    ThreadPoolSyncJobDispatcher,
)
from app.connectors import GithubConnector
from app.db import SessionLocal
from app.repositories import (
    SqlAlchemyCodeRepoRepository,
    SqlAlchemyContextDataRepository,
    SqlAlchemySystemComponentRepository,
    SystemComponentRepository,
)

_sync_executor = ThreadPoolExecutor(max_workers=2)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_system_component_repository(
    db: Session = Depends(get_db),
) -> SystemComponentRepository:
    return SqlAlchemySystemComponentRepository(db)


def get_code_repo_repository(db: Session = Depends(get_db)):
    return SqlAlchemyCodeRepoRepository(db)


def get_context_data_repository(db: Session = Depends(get_db)):
    return SqlAlchemyContextDataRepository(db)


def get_system_component_service(
    repository: SystemComponentRepository = Depends(get_system_component_repository),
) -> SystemComponentService:
    return SystemComponentService(repository)


def get_code_repo_service(
    code_repo_repository=Depends(get_code_repo_repository),
    system_component_repository: SystemComponentRepository = Depends(
        get_system_component_repository
    ),
) -> CodeRepoService:
    return CodeRepoService(code_repo_repository, system_component_repository)


def get_context_service(
    context_repository=Depends(get_context_data_repository),
) -> ContextService:
    return ContextService(context_repository)


def get_github_connector() -> GithubConnector:
    return GithubConnector()


def get_sync_job_dispatcher() -> SyncJobDispatcher:
    return ThreadPoolSyncJobDispatcher(executor=_sync_executor)


def get_connector_registry(
    github_connector: GithubConnector = Depends(get_github_connector),
):
    return {"github": github_connector}


def get_context_repository_scope():
    @contextmanager
    def scope() -> Iterator[SqlAlchemyContextDataRepository]:
        db = SessionLocal()
        try:
            yield SqlAlchemyContextDataRepository(db)
        finally:
            db.close()

    return scope


def get_sync_service(
    context_repository=Depends(get_context_data_repository),
    connectors=Depends(get_connector_registry),
    job_dispatcher: SyncJobDispatcher = Depends(get_sync_job_dispatcher),
    repository_scope=Depends(get_context_repository_scope),
) -> SyncService:
    return SyncService(
        context_repository=context_repository,
        connectors=connectors,
        job_dispatcher=job_dispatcher,
        repository_scope=repository_scope,
    )
