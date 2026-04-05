import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Callable, Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application import (
    CodeRepoService,
    ContextService,
    GithubNormalizationService,
    RenderRuntimeNormalizationService,
    SyncJobDispatcher,
    SyncService,
    SystemComponentService,
    ThreadPoolSyncJobDispatcher,
)
from app.application.sync_runtime import SyncRuntimeState
from app.connectors import GithubConnector, RenderRuntimeConnector
from app.db import SessionLocal
from app.repositories import (
    SqlAlchemyCodeRepoRepository,
    SqlAlchemyContextEntityRepository,
    SqlAlchemyContextQueryRepository,
    SqlAlchemyGithubNormalizationRepository,
    SqlAlchemySyncRepository,
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


def get_context_entity_repository(db: Session = Depends(get_db)):
    return SqlAlchemyContextEntityRepository(db)


def get_sync_repository(db: Session = Depends(get_db)):
    return SqlAlchemySyncRepository(db)


def get_context_query_repository(db: Session = Depends(get_db)):
    return SqlAlchemyContextQueryRepository(db)


def get_github_normalization_repository(db: Session = Depends(get_db)):
    return SqlAlchemyGithubNormalizationRepository(db)


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
    context_query_repository=Depends(get_context_query_repository),
) -> ContextService:
    return ContextService(context_query_repository)


def get_mcp_api_token() -> str | None:
    token = os.getenv("MCP_API_TOKEN", "").strip()
    return token or None


def get_mcp_tool_timeout_seconds() -> float:
    return float(os.getenv("MCP_TOOL_TIMEOUT_SECONDS", "5"))


def get_github_normalization_service(
    normalization_repository=Depends(get_github_normalization_repository),
) -> GithubNormalizationService:
    return GithubNormalizationService(normalization_repository)


def get_github_connector() -> GithubConnector:
    repos_raw = os.getenv("GITHUB_REPOS", "")
    repos = [item.strip() for item in repos_raw.split(",") if item.strip()]
    return GithubConnector(
        token=os.getenv("GITHUB_TOKEN"),
        owner=os.getenv("GITHUB_OWNER"),
        repos=repos,
        per_page=int(os.getenv("GITHUB_PER_PAGE", "20")),
        max_pages=int(os.getenv("GITHUB_MAX_PAGES", "10")),
        lookback_minutes=int(os.getenv("GITHUB_SYNC_LOOKBACK_MINUTES", "60")),
    )


def _parse_render_service_component_map(value: str) -> dict[str, str]:
    pairs = [item.strip() for item in value.split(",") if item.strip()]
    parsed: dict[str, str] = {}
    for pair in pairs:
        if ":" not in pair:
            continue
        service_id, component_name = pair.split(":", 1)
        normalized_service_id = service_id.strip()
        normalized_component_name = component_name.strip()
        if not normalized_service_id or not normalized_component_name:
            continue
        parsed[normalized_service_id] = normalized_component_name
    return parsed


def get_render_runtime_connector() -> RenderRuntimeConnector:
    service_ids_raw = os.getenv("RENDER_SERVICE_IDS", "")
    service_ids = [item.strip() for item in service_ids_raw.split(",") if item.strip()]
    service_component_map_raw = os.getenv("RENDER_SERVICE_COMPONENT_MAP", "")
    service_component_map = _parse_render_service_component_map(service_component_map_raw)
    return RenderRuntimeConnector(
        api_token=os.getenv("RENDER_API_KEY"),
        service_ids=service_ids,
        service_component_map=service_component_map,
        environment=os.getenv("RENDER_RUNTIME_ENVIRONMENT", "staging"),
        timeout_seconds=float(os.getenv("RENDER_TIMEOUT_SECONDS", "10")),
    )


def get_sync_job_dispatcher() -> SyncJobDispatcher:
    return ThreadPoolSyncJobDispatcher(executor=_sync_executor)


def get_sync_runtime_state() -> SyncRuntimeState:
    return _sync_runtime_state


def get_connector_registry(
    github_connector: GithubConnector = Depends(get_github_connector),
    render_runtime_connector: RenderRuntimeConnector = Depends(
        get_render_runtime_connector
    ),
):
    return {"github": github_connector, "render-runtime": render_runtime_connector}


def get_sync_normalizer_factories():
    return {
        "github": lambda sync_repo: GithubNormalizationService(
            SqlAlchemyGithubNormalizationRepository(sync_repo.db)
        ),
        "render-runtime": lambda sync_repo: RenderRuntimeNormalizationService(
            SqlAlchemyGithubNormalizationRepository(sync_repo.db)
        ),
    }


def get_sync_strict_normalization_enabled() -> bool:
    raw_value = os.getenv("SYNC_STRICT_NORMALIZATION", "false").strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def get_sync_repository_scope():
    @contextmanager
    def scope() -> Iterator[SqlAlchemySyncRepository]:
        db = SessionLocal()
        try:
            yield SqlAlchemySyncRepository(db)
        finally:
            db.close()

    return scope


def get_sync_service(
    sync_repository=Depends(get_sync_repository),
    connectors=Depends(get_connector_registry),
    normalizer_factories=Depends(get_sync_normalizer_factories),
    strict_normalization=Depends(get_sync_strict_normalization_enabled),
    job_dispatcher: SyncJobDispatcher = Depends(get_sync_job_dispatcher),
    repository_scope=Depends(get_sync_repository_scope),
    runtime_state: SyncRuntimeState = Depends(get_sync_runtime_state),
) -> SyncService:
    return SyncService(
        sync_repository=sync_repository,
        connectors=connectors,
        normalizer_factories=normalizer_factories,
        strict_normalization=strict_normalization,
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
    scope_factory = get_sync_repository_scope()
    with scope_factory() as sync_repository:
        sync_service = SyncService(
            sync_repository=sync_repository,
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
