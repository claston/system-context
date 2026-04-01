from concurrent.futures import Executor
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from app.connectors.base import ConnectorRunRequest


class SyncExecutionError(Exception):
    pass


class SyncRunNotFoundError(Exception):
    pass


class SyncJobDispatcher:
    def dispatch_github_sync(
        self,
        task: Callable[[UUID, str | None], object],
        sync_run_id: UUID,
        system_component_name: str | None = None,
    ):
        raise NotImplementedError


class ThreadPoolSyncJobDispatcher(SyncJobDispatcher):
    def __init__(self, executor: Executor) -> None:
        self.executor = executor

    def dispatch_github_sync(
        self,
        task: Callable[[UUID, str | None], object],
        sync_run_id: UUID,
        system_component_name: str | None = None,
    ):
        self.executor.submit(task, sync_run_id, system_component_name)


class SyncService:
    def __init__(self, context_repository, github_connector, job_dispatcher: SyncJobDispatcher) -> None:
        self.context_repository = context_repository
        self.github_connector = github_connector
        self.job_dispatcher = job_dispatcher

    def trigger_github_sync(self, system_component_name: str | None = None):
        sync_run = self.context_repository.create_sync_run(
            connector_name="github",
            status="running",
            records_processed=0,
            started_at=datetime.now(timezone.utc),
        )
        sync_run_id = sync_run["id"] if isinstance(sync_run, dict) else sync_run.id
        self.job_dispatcher.dispatch_github_sync(
            self.execute_github_sync,
            sync_run_id,
            system_component_name,
        )
        return sync_run

    def execute_github_sync(self, sync_run_id: UUID, system_component_name: str | None = None):
        try:
            batch = self.github_connector.collect(
                ConnectorRunRequest(system_component_name=system_component_name)
            )
            return self.context_repository.update_sync_run(
                sync_run_id,
                status="success",
                records_processed=batch.records_processed,
                finished_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            return self.context_repository.update_sync_run(
                sync_run_id,
                status="failed",
                records_processed=0,
                error_summary=str(exc),
                finished_at=datetime.now(timezone.utc),
            )

    def get_sync_run(self, sync_run_id: UUID):
        item = self.context_repository.get_sync_run_by_id(sync_run_id)
        if item is None:
            raise SyncRunNotFoundError(f"sync run not found: {sync_run_id}")
        return item
