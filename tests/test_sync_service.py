from datetime import datetime, timezone
from typing import Iterator
from uuid import UUID, uuid4

from app.application.sync_service import SyncExecutionError, SyncRunNotFoundError, SyncService
from app.connectors.base import ConnectorBatch, ConnectorRunRequest


class FakeContextRepository:
    def __init__(self):
        self.created = []
        self.by_id = {}
        self.raw_events = []
        self.updated = []

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
        self.by_id[payload["id"]] = payload
        return payload

    def get_sync_run_by_id(self, sync_run_id: UUID):
        return self.by_id.get(sync_run_id)

    def update_sync_run(self, sync_run_id: UUID, **kwargs):
        item = self.by_id[sync_run_id]
        item.update(kwargs)
        item["updated_at"] = datetime.now(timezone.utc)
        self.updated.append({"sync_run_id": sync_run_id, **kwargs})
        return item

    def create_connector_raw_events(self, sync_run_id: UUID, connector_name: str, items):
        for item in items:
            self.raw_events.append(
                {
                    "sync_run_id": sync_run_id,
                    "connector_name": connector_name,
                    "payload": item,
                }
            )
        return self.raw_events


class FakeSyncJobDispatcher:
    def __init__(self) -> None:
        self.jobs = []

    def dispatch_sync(
        self,
        task,
        sync_run_id: UUID,
        connector_name: str,
        request: ConnectorRunRequest,
    ):
        self.jobs.append(
            {
                "task": task,
                "sync_run_id": sync_run_id,
                "connector_name": connector_name,
                "request": request,
            }
        )


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


class FakeRepositoryScope:
    def __init__(self, repo: FakeContextRepository) -> None:
        self.repo = repo
        self.open_calls = 0

    def __call__(self) -> Iterator[FakeContextRepository]:
        self.open_calls += 1
        yield self.repo


def test_sync_service_triggers_running_and_dispatches_job() -> None:
    repo = FakeContextRepository()
    dispatcher = FakeSyncJobDispatcher()
    service = SyncService(
        context_repository=repo,
        connectors={"github": FakeGithubConnector()},
        job_dispatcher=dispatcher,
    )

    result = service.trigger_sync(
        connector_name="github",
        request=ConnectorRunRequest(system_component_name="payment-api"),
    )

    assert result["status"] == "running"
    assert result["records_processed"] == 0
    assert result["connector_name"] == "github"
    assert len(repo.created) == 1
    assert repo.created[0]["status"] == "running"
    assert len(dispatcher.jobs) == 1
    assert dispatcher.jobs[0]["sync_run_id"] == result["id"]
    assert dispatcher.jobs[0]["connector_name"] == "github"
    assert dispatcher.jobs[0]["request"].system_component_name == "payment-api"


def test_sync_service_executes_and_marks_success() -> None:
    repo = FakeContextRepository()
    dispatcher = FakeSyncJobDispatcher()
    service = SyncService(
        context_repository=repo,
        connectors={"github": FakeGithubConnector()},
        job_dispatcher=dispatcher,
    )
    running = service.trigger_sync(
        connector_name="github",
        request=ConnectorRunRequest(system_component_name="payment-api"),
    )

    result = service.execute_sync(
        sync_run_id=running["id"],
        connector_name="github",
        request=ConnectorRunRequest(system_component_name="payment-api"),
    )

    assert result["status"] == "success"
    assert result["records_processed"] == 2
    assert result["finished_at"] is not None
    assert len(repo.raw_events) == 2
    assert repo.raw_events[0]["sync_run_id"] == running["id"]


def test_sync_service_executes_and_marks_failed() -> None:
    repo = FakeContextRepository()
    dispatcher = FakeSyncJobDispatcher()
    service = SyncService(
        context_repository=repo,
        connectors={"github": FakeGithubConnector(should_fail=True)},
        job_dispatcher=dispatcher,
    )
    running = service.trigger_sync(
        connector_name="github",
        request=ConnectorRunRequest(system_component_name="payment-api"),
    )

    result = service.execute_sync(
        sync_run_id=running["id"],
        connector_name="github",
        request=ConnectorRunRequest(system_component_name="payment-api"),
    )

    assert result["status"] == "failed"
    assert result["records_processed"] == 0
    assert "connector failed" in (result["error_summary"] or "")


def test_sync_service_get_sync_run_raises_when_not_found() -> None:
    repo = FakeContextRepository()
    dispatcher = FakeSyncJobDispatcher()
    service = SyncService(
        context_repository=repo,
        connectors={"github": FakeGithubConnector()},
        job_dispatcher=dispatcher,
    )

    missing_id = uuid4()
    try:
        service.get_sync_run(missing_id)
    except SyncRunNotFoundError as exc:
        assert str(missing_id) in str(exc)
    else:
        raise AssertionError("expected SyncRunNotFoundError")


def test_execute_sync_uses_repository_scope_for_background_updates() -> None:
    request_repo = FakeContextRepository()
    worker_repo = FakeContextRepository()
    dispatcher = FakeSyncJobDispatcher()
    scope = FakeRepositoryScope(worker_repo)
    service = SyncService(
        context_repository=request_repo,
        connectors={"github": FakeGithubConnector()},
        job_dispatcher=dispatcher,
        repository_scope=scope,
    )
    running = service.trigger_sync(
        connector_name="github",
        request=ConnectorRunRequest(system_component_name="payment-api"),
    )
    worker_repo.by_id[running["id"]] = dict(running)

    result = service.execute_sync(
        sync_run_id=running["id"],
        connector_name="github",
        request=ConnectorRunRequest(system_component_name="payment-api"),
    )

    assert scope.open_calls == 1
    assert result["status"] == "success"
    assert len(worker_repo.updated) == 1
    assert len(worker_repo.raw_events) == 2
    assert len(request_repo.updated) == 0
    assert len(request_repo.raw_events) == 0
