from fastapi import Depends
from sqlalchemy.orm import Session

from app.application import CodeRepoService, ContextService, SyncService, SystemComponentService
from app.connectors import GithubConnector
from app.db import SessionLocal
from app.repositories import (
    SqlAlchemyCodeRepoRepository,
    SqlAlchemyContextDataRepository,
    SqlAlchemySystemComponentRepository,
    SystemComponentRepository,
)


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


def get_sync_service(
    context_repository=Depends(get_context_data_repository),
    github_connector: GithubConnector = Depends(get_github_connector),
) -> SyncService:
    return SyncService(context_repository=context_repository, github_connector=github_connector)
