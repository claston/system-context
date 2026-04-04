import logging
from concurrent.futures import Executor
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, ContextManager
from uuid import UUID

from app.application.sync_runtime import SyncRuntimeState
from app.connectors.base import ConnectorRunRequest
from app.repositories import SyncRepository

logger = logging.getLogger(__name__)


class SyncExecutionError(Exception):
    pass


class SyncRunNotFoundError(Exception):
    pass


class UnknownConnectorError(Exception):
    pass


class SyncShuttingDownError(Exception):
    pass


class SyncJobDispatcher:
    def dispatch_sync(
        self,
        task: Callable[[UUID, str, ConnectorRunRequest], object],
        sync_run_id: UUID,
        connector_name: str,
        request: ConnectorRunRequest,
    ):
        raise NotImplementedError


class ThreadPoolSyncJobDispatcher(SyncJobDispatcher):
    def __init__(self, executor: Executor) -> None:
        self.executor = executor

    def dispatch_sync(
        self,
        task: Callable[[UUID, str, ConnectorRunRequest], object],
        sync_run_id: UUID,
        connector_name: str,
        request: ConnectorRunRequest,
    ):
        self.executor.submit(task, sync_run_id, connector_name, request)


class SyncService:
    def __init__(
        self,
        sync_repository: SyncRepository,
        connectors,
        job_dispatcher: SyncJobDispatcher,
        repository_scope: Callable[[], ContextManager] | None = None,
        runtime_state: SyncRuntimeState | None = None,
        normalizer_factories: dict[str, Callable[[Any], Any]] | None = None,
        strict_normalization: bool = False,
    ) -> None:
        self.sync_repository = sync_repository
        self.connectors = connectors
        self.job_dispatcher = job_dispatcher
        self.repository_scope = repository_scope
        self.runtime_state = runtime_state
        self.normalizer_factories = normalizer_factories or {}
        self.strict_normalization = strict_normalization

    def trigger_sync(self, connector_name: str, request: ConnectorRunRequest):
        if self.runtime_state and self.runtime_state.is_shutting_down():
            raise SyncShuttingDownError("sync service is shutting down")
        if connector_name not in self.connectors:
            raise UnknownConnectorError(f"unknown connector: {connector_name}")
        sync_run = self.sync_repository.create_sync_run(
            connector_name=connector_name,
            status="running",
            records_processed=0,
            started_at=datetime.now(timezone.utc),
        )
        sync_run_id = sync_run["id"] if isinstance(sync_run, dict) else sync_run.id
        self.job_dispatcher.dispatch_sync(
            self.execute_sync,
            sync_run_id,
            connector_name,
            request,
        )
        return sync_run

    @contextmanager
    def _repository_context(self):
        if self.repository_scope is None:
            yield self.sync_repository
            return
        with self.repository_scope() as repo:
            yield repo

    def execute_sync(
        self, sync_run_id: UUID, connector_name: str, request: ConnectorRunRequest
    ):
        if self.runtime_state and not self.runtime_state.try_acquire_job_slot():
            return self._mark_sync_run_failed(
                sync_run_id=sync_run_id,
                error_summary="interrupted by shutdown",
            )
        connector = self.connectors.get(connector_name)
        if connector is None:
            return self._mark_sync_run_failed(
                sync_run_id=sync_run_id,
                error_summary=f"unknown connector: {connector_name}",
            )

        logger.info(
            "Starting sync run execution",
            extra={"sync_run_id": str(sync_run_id), "connector_name": connector_name},
        )
        try:
            with self._repository_context() as repo:
                cursor_by_target = repo.get_connector_sync_cursors(connector_name)
            batch = connector.collect(
                ConnectorRunRequest(
                    system_component_name=request.system_component_name,
                    cursor_by_target=cursor_by_target,
                )
            )
            with self._repository_context() as repo:
                inserted_events_count = 0
                processed_records_count = max(0, batch.records_processed)
                warning_summary = list(getattr(batch, "warnings", []))
                if batch.items:
                    inserted_events = repo.create_connector_raw_events(
                        sync_run_id=sync_run_id,
                        connector_name=connector_name,
                        items=batch.items,
                    )
                    inserted_events_count = len(inserted_events)
                if batch.latest_cursor_by_target:
                    repo.upsert_connector_sync_cursors(
                        connector_name=connector_name,
                        cursor_by_target=batch.latest_cursor_by_target,
                    )
                all_errors = list(batch.errors)
                if connector_name in self.normalizer_factories:
                    try:
                        normalizer = self.normalizer_factories[connector_name](repo)
                        normalization_summary = normalizer.normalize_sync_run(sync_run_id)
                        if isinstance(normalization_summary, dict):
                            normalization_errors = normalization_summary.get("errors") or []
                            normalization_skipped = int(
                                normalization_summary.get("skipped") or 0
                            )
                            has_normalization_issues = bool(normalization_errors) or normalization_skipped > 0
                            if has_normalization_issues:
                                message = (
                                    "normalization reported issues: "
                                    f"skipped={normalization_skipped}, errors={len(normalization_errors)}"
                                )
                                if self.strict_normalization:
                                    all_errors.append(message)
                                else:
                                    warning_summary.append(message)
                    except Exception as exc:
                        all_errors.append(
                            f"normalization failed: {type(exc).__name__}: {exc}"
                        )
                has_success_signal = (
                    processed_records_count > 0 or inserted_events_count > 0
                )
                if all_errors:
                    status = "partial" if has_success_signal else "failed"
                else:
                    status = "success"

                counter_summary = (
                    f"processed={processed_records_count}, inserted={inserted_events_count}"
                )
                if all_errors:
                    error_summary = "; ".join([*all_errors, counter_summary])
                else:
                    error_summary = None
                if warning_summary:
                    logger.warning(
                        "Sync run completed with warnings",
                        extra={
                            "sync_run_id": str(sync_run_id),
                            "connector_name": connector_name,
                            "warnings": warning_summary,
                            "counter_summary": counter_summary,
                        },
                    )
                elif status == "success" and processed_records_count != inserted_events_count:
                    logger.info(
                        "Sync run completed with deduped records",
                        extra={
                            "sync_run_id": str(sync_run_id),
                            "connector_name": connector_name,
                            "counter_summary": counter_summary,
                        },
                    )
                return repo.update_sync_run(
                    sync_run_id,
                    status=status,
                    records_processed=processed_records_count,
                    error_summary=error_summary,
                    finished_at=datetime.now(timezone.utc),
                )
        except Exception as exc:
            logger.exception(
                "Sync run execution failed",
                extra={"sync_run_id": str(sync_run_id), "connector_name": connector_name},
            )
            return self._mark_sync_run_failed(
                sync_run_id=sync_run_id,
                error_summary=f"{type(exc).__name__}: {exc}",
            )
        finally:
            if self.runtime_state:
                self.runtime_state.release_job_slot()

    def _mark_sync_run_failed(self, sync_run_id: UUID, error_summary: str):
        with self._repository_context() as repo:
            return repo.update_sync_run(
                sync_run_id,
                status="failed",
                records_processed=0,
                error_summary=error_summary,
                finished_at=datetime.now(timezone.utc),
            )

    def mark_running_sync_runs_failed(self, error_summary: str) -> int:
        with self._repository_context() as repo:
            running_sync_runs = repo.list_sync_runs_by_status("running")
            for sync_run in running_sync_runs:
                sync_run_id = (
                    sync_run["id"] if isinstance(sync_run, dict) else sync_run.id
                )
                repo.update_sync_run(
                    sync_run_id,
                    status="failed",
                    records_processed=0,
                    error_summary=error_summary,
                    finished_at=datetime.now(timezone.utc),
                )
            return len(running_sync_runs)

    def get_sync_run(self, sync_run_id: UUID):
        item = self.sync_repository.get_sync_run_by_id(sync_run_id)
        if item is None:
            raise SyncRunNotFoundError(f"sync run not found: {sync_run_id}")
        return item
