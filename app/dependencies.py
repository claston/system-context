import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Callable, Iterator

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
from app.application.sync_runtime import SyncRuntimeState
from app.connectors import GithubConnector
from app.db import SessionLocal
from app.repositories import (
    SqlAlchemyCodeRepoRepository,
    SqlAlchemyContextDataRepository,
    SqlAlchemySystemComponentRepository,
    SystemComponentRepository,
)

_sync_executor = ThreadPoolExecutor(max_workers=2)
_sync_runtime_state = SyncRuntimeState()


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
    repos_raw = os.getenv("GITHUB_REPOS", "")
    repos = [item.strip() for item in repos_raw.split(",") if item.strip()]
    return GithubConnector(
        token=os.getenv("GITHUB_TOKEN"),
        owner=os.getenv("GITHUB_OWNER"),
        repos=repos,
        per_page=int(os.getenv("GITHUB_PER_PAGE", "20")),
    )


def get_sync_job_dispatcher() -> SyncJobDispatcher:
    return ThreadPoolSyncJobDispatcher(executor=_sync_executor)


def get_sync_runtime_state() -> SyncRuntimeState:
    return _sync_runtime_state


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
    runtime_state: SyncRuntimeState = Depends(get_sync_runtime_state),
) -> SyncService:
    return SyncService(
        context_repository=context_repository,
        connectors=connectors,
        job_dispatcher=job_dispatcher,
        repository_scope=repository_scope,
        runtime_state=runtime_state,
    )


def get_sync_shutdown_timeout_seconds() -> float:
    return float(os.getenv("SYNC_SHUTDOWN_TIMEOUT_SECONDS", "15"))


def get_sync_recovery_enabled() -> bool:
    raw_value = os.getenv("SYNC_RECOVERY_ENABLED", "true").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


class _NoopSyncJobDispatcher(SyncJobDispatcher):
    def dispatch_sync(
        self,
        task: Callable,
        sync_run_id,
        connector_name: str,
        request,
    ):
        return None


def _mark_running_sync_runs_failed(error_summary: str) -> int:
    scope_factory = get_context_repository_scope()
    with scope_factory() as context_repository:
        sync_service = SyncService(
            context_repository=context_repository,
            connectors={},
            job_dispatcher=_NoopSyncJobDispatcher(),
            repository_scope=None,
            runtime_state=None,
        )
        return sync_service.mark_running_sync_runs_failed(error_summary=error_summary)


def startup_sync_recovery() -> int:
    _sync_runtime_state.reset_startup()
    if not get_sync_recovery_enabled():
        return 0
    return _mark_running_sync_runs_failed(
        error_summary="recovered on startup after unclean stop"
    )


def shutdown_sync_execution() -> int:
    _sync_runtime_state.begin_shutdown()
    _sync_runtime_state.wait_for_idle(get_sync_shutdown_timeout_seconds())
    return _mark_running_sync_runs_failed(error_summary="interrupted by shutdown")
