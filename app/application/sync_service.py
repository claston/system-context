import logging
from concurrent.futures import Executor
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, ContextManager
from uuid import UUID

from app.connectors.base import ConnectorRunRequest

logger = logging.getLogger(__name__)


class SyncExecutionError(Exception):
    pass


class SyncRunNotFoundError(Exception):
    pass


class UnknownConnectorError(Exception):
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
        context_repository,
        connectors,
        job_dispatcher: SyncJobDispatcher,
        repository_scope: Callable[[], ContextManager] | None = None,
    ) -> None:
        self.context_repository = context_repository
        self.connectors = connectors
        self.job_dispatcher = job_dispatcher
        self.repository_scope = repository_scope

    def trigger_sync(self, connector_name: str, request: ConnectorRunRequest):
        if connector_name not in self.connectors:
            raise UnknownConnectorError(f"unknown connector: {connector_name}")
        sync_run = self.context_repository.create_sync_run(
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
            yield self.context_repository
            return
        with self.repository_scope() as repo:
            yield repo

    def execute_sync(
        self, sync_run_id: UUID, connector_name: str, request: ConnectorRunRequest
    ):
        connector = self.connectors.get(connector_name)
        if connector is None:
            with self._repository_context() as repo:
                return repo.update_sync_run(
                    sync_run_id,
                    status="failed",
                    records_processed=0,
                    error_summary=f"unknown connector: {connector_name}",
                    finished_at=datetime.now(timezone.utc),
                )

        logger.info(
            "Starting sync run execution",
            extra={"sync_run_id": str(sync_run_id), "connector_name": connector_name},
        )
        try:
            batch = connector.collect(request)
            with self._repository_context() as repo:
                if batch.items:
                    repo.create_connector_raw_events(
                        sync_run_id=sync_run_id,
                        connector_name=connector_name,
                        items=batch.items,
                    )
                error_summary = "; ".join(batch.errors) if batch.errors else None
                return repo.update_sync_run(
                    sync_run_id,
                    status="success",
                    records_processed=batch.records_processed,
                    error_summary=error_summary,
                    finished_at=datetime.now(timezone.utc),
                )
        except Exception as exc:
            logger.exception(
                "Sync run execution failed",
                extra={"sync_run_id": str(sync_run_id), "connector_name": connector_name},
            )
            with self._repository_context() as repo:
                return repo.update_sync_run(
                    sync_run_id,
                    status="failed",
                    records_processed=0,
                    error_summary=f"{type(exc).__name__}: {exc}",
                    finished_at=datetime.now(timezone.utc),
                )

    def get_sync_run(self, sync_run_id: UUID):
        item = self.context_repository.get_sync_run_by_id(sync_run_id)
        if item is None:
            raise SyncRunNotFoundError(f"sync run not found: {sync_run_id}")
        return item
