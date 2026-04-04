from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator
from uuid import UUID, uuid4

from app.application.sync_runtime import SyncRuntimeState
from app.application.sync_service import (
    SyncExecutionError,
    SyncRunNotFoundError,
    SyncService,
    SyncShuttingDownError,
)
from app.connectors.base import ConnectorBatch, ConnectorRunRequest


class FakeContextRepository:
    def __init__(self):
        self.created = []
        self.by_id = {}
        self.raw_events = []
        self.updated = []
        self.cursor_by_target = {}
        self.requested_connector_names = []
        self.upserted_cursors = []

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

    def list_sync_runs_by_status(self, status: str):
        return [item for item in self.by_id.values() if item.get("status") == status]

    def get_connector_sync_cursors(self, connector_name: str) -> dict[str, str]:
        self.requested_connector_names.append(connector_name)
        return dict(self.cursor_by_target)

    def upsert_connector_sync_cursors(
        self, connector_name: str, cursor_by_target: dict[str, str]
    ) -> None:
        self.upserted_cursors.append(
            {"connector_name": connector_name, "cursor_by_target": dict(cursor_by_target)}
        )
        self.cursor_by_target.update(cursor_by_target)


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
        self.requests = []

    def collect(self, request: ConnectorRunRequest) -> ConnectorBatch:
        if self.should_fail:
            raise SyncExecutionError("connector failed")
        self.requests.append(request)
        return ConnectorBatch(
            connector_name="github",
            records_processed=2,
            items=[{"kind": "pull_request"}, {"kind": "commit"}],
            latest_cursor_by_target={"acme/payment-api": "2026-04-03T12:02:00+00:00"},
        )


class FakeRepositoryScope:
    def __init__(self, repo: FakeContextRepository) -> None:
        self.repo = repo
        self.open_calls = 0

    def __call__(self):
        @contextmanager
        def scope() -> Iterator[FakeContextRepository]:
            self.open_calls += 1
            yield self.repo

        return scope()


class FakeNormalizer:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls = []

    def normalize_sync_run(self, sync_run_id: UUID):
        self.calls.append(sync_run_id)
        if self.should_fail:
            raise RuntimeError("normalization boom")
        return {"sync_run_id": sync_run_id}


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
    connector = FakeGithubConnector()
    service = SyncService(
        context_repository=repo,
        connectors={"github": connector},
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
    assert repo.requested_connector_names == ["github"]
    assert len(repo.upserted_cursors) == 1
    assert repo.upserted_cursors[0]["connector_name"] == "github"
    assert connector.requests[0].cursor_by_target == {}


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

    assert scope.open_calls == 2
    assert result["status"] == "success"
    assert len(worker_repo.updated) == 1
    assert len(worker_repo.raw_events) == 2
    assert len(request_repo.updated) == 0
    assert len(request_repo.raw_events) == 0


def test_execute_sync_passes_existing_cursor_to_connector() -> None:
    repo = FakeContextRepository()
    repo.cursor_by_target = {"acme/payment-api": "2026-04-03T12:00:30Z"}
    dispatcher = FakeSyncJobDispatcher()
    connector = FakeGithubConnector()
    service = SyncService(
        context_repository=repo,
        connectors={"github": connector},
        job_dispatcher=dispatcher,
    )
    running = service.trigger_sync(
        connector_name="github",
        request=ConnectorRunRequest(system_component_name="payment-api"),
    )

    service.execute_sync(
        sync_run_id=running["id"],
        connector_name="github",
        request=ConnectorRunRequest(system_component_name="payment-api"),
    )

    assert connector.requests[0].cursor_by_target == {
        "acme/payment-api": "2026-04-03T12:00:30Z"
    }


def test_execute_sync_runs_registered_normalizer_after_successful_ingestion() -> None:
    repo = FakeContextRepository()
    dispatcher = FakeSyncJobDispatcher()
    connector = FakeGithubConnector()
    normalizer = FakeNormalizer()
    service = SyncService(
        context_repository=repo,
        connectors={"github": connector},
        job_dispatcher=dispatcher,
        normalizer_factories={"github": lambda _repo: normalizer},
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
    assert normalizer.calls == [running["id"]]


def test_execute_sync_marks_partial_when_normalization_fails() -> None:
    repo = FakeContextRepository()
    dispatcher = FakeSyncJobDispatcher()
    connector = FakeGithubConnector()
    normalizer = FakeNormalizer(should_fail=True)
    service = SyncService(
        context_repository=repo,
        connectors={"github": connector},
        job_dispatcher=dispatcher,
        normalizer_factories={"github": lambda _repo: normalizer},
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

    assert result["status"] == "partial"
    assert result["records_processed"] == 2
    assert "normalization failed: RuntimeError: normalization boom" in (
        result["error_summary"] or ""
    )


def test_trigger_sync_rejects_when_app_is_shutting_down() -> None:
    repo = FakeContextRepository()
    dispatcher = FakeSyncJobDispatcher()
    runtime_state = SyncRuntimeState()
    runtime_state.begin_shutdown()
    service = SyncService(
        context_repository=repo,
        connectors={"github": FakeGithubConnector()},
        job_dispatcher=dispatcher,
        runtime_state=runtime_state,
    )

    try:
        service.trigger_sync(
            connector_name="github",
            request=ConnectorRunRequest(system_component_name="payment-api"),
        )
    except SyncShuttingDownError:
        pass
    else:
        raise AssertionError("expected SyncShuttingDownError")

    assert len(repo.created) == 0
    assert len(dispatcher.jobs) == 0


def test_execute_sync_marks_failed_when_shutdown_started_before_job() -> None:
    repo = FakeContextRepository()
    dispatcher = FakeSyncJobDispatcher()
    runtime_state = SyncRuntimeState()
    service = SyncService(
        context_repository=repo,
        connectors={"github": FakeGithubConnector()},
        job_dispatcher=dispatcher,
        runtime_state=runtime_state,
    )
    running = repo.create_sync_run(
        connector_name="github",
        status="running",
        records_processed=0,
        started_at=datetime.now(timezone.utc),
    )
    runtime_state.begin_shutdown()

    result = service.execute_sync(
        sync_run_id=running["id"],
        connector_name="github",
        request=ConnectorRunRequest(system_component_name="payment-api"),
    )

    assert result["status"] == "failed"
    assert result["finished_at"] is not None
    assert "interrupted by shutdown" in (result["error_summary"] or "")
    assert len(repo.raw_events) == 0


def test_mark_running_sync_runs_failed_updates_orphaned_runs() -> None:
    repo = FakeContextRepository()
    dispatcher = FakeSyncJobDispatcher()
    service = SyncService(
        context_repository=repo,
        connectors={"github": FakeGithubConnector()},
        job_dispatcher=dispatcher,
    )
    running = repo.create_sync_run(
        connector_name="github",
        status="running",
        records_processed=0,
        started_at=datetime.now(timezone.utc),
    )
    repo.create_sync_run(
        connector_name="github",
        status="success",
        records_processed=2,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )

    updated_count = service.mark_running_sync_runs_failed(
        error_summary="recovered on startup after unclean stop"
    )

    assert updated_count == 1
    assert repo.by_id[running["id"]]["status"] == "failed"
    assert repo.by_id[running["id"]]["finished_at"] is not None
    assert "recovered on startup" in (repo.by_id[running["id"]]["error_summary"] or "")
