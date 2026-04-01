from datetime import datetime, timezone

from app.connectors.base import ConnectorRunRequest


class SyncExecutionError(Exception):
    pass


class SyncService:
    def __init__(self, context_repository, github_connector) -> None:
        self.context_repository = context_repository
        self.github_connector = github_connector

    def run_github_sync(self, system_component_name: str | None = None):
        started_at = datetime.now(timezone.utc)
        self.context_repository.create_sync_run(
            connector_name="github",
            status="running",
            records_processed=0,
            started_at=started_at,
        )
        try:
            batch = self.github_connector.collect(
                ConnectorRunRequest(system_component_name=system_component_name)
            )
            return self.context_repository.create_sync_run(
                connector_name="github",
                status="success",
                records_processed=batch.records_processed,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            return self.context_repository.create_sync_run(
                connector_name="github",
                status="failed",
                records_processed=0,
                error_summary=str(exc),
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
