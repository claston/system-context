from datetime import datetime, timezone
from uuid import uuid4

from app.application.sync_service import SyncExecutionError, SyncService
from app.connectors.base import ConnectorBatch, ConnectorRunRequest


class FakeContextRepository:
    def __init__(self):
        self.created = []

    def create_sync_run(self, **kwargs):
        payload = {
            "id": uuid4(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "finished_at": None,
            "error_summary": None,
            **kwargs,
        }
        self.created.append(payload)
        return payload


class FakeGithubConnector:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def collect(self, request: ConnectorRunRequest) -> ConnectorBatch:
        if self.should_fail:
            raise SyncExecutionError("connector failed")
        return ConnectorBatch(
            connector_name="github",
            records_processed=2,
            items=[{"kind": "pull_request"}, {"kind": "commit"}],
        )


def test_sync_service_records_running_and_success() -> None:
    repo = FakeContextRepository()
    service = SyncService(context_repository=repo, github_connector=FakeGithubConnector())

    result = service.run_github_sync(system_component_name="payment-api")

    assert result["status"] == "success"
    assert result["records_processed"] == 2
    assert result["connector_name"] == "github"
    assert len(repo.created) == 2
    assert repo.created[0]["status"] == "running"
    assert repo.created[1]["status"] == "success"


def test_sync_service_records_running_and_failed() -> None:
    repo = FakeContextRepository()
    service = SyncService(
        context_repository=repo,
        github_connector=FakeGithubConnector(should_fail=True),
    )

    result = service.run_github_sync(system_component_name="payment-api")

    assert result["status"] == "failed"
    assert result["records_processed"] == 0
    assert "connector failed" in (result["error_summary"] or "")
    assert len(repo.created) == 2
    assert repo.created[0]["status"] == "running"
    assert repo.created[1]["status"] == "failed"
