from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.connectors.base import ConnectorBatch
from app.db import Base
from app.dependencies import (
    get_db,
    get_github_connector,
    get_sync_job_dispatcher,
    get_sync_repository_scope,
)
from app.main import app
from app.repositories import SqlAlchemySyncRepository


class FakeGithubConnector:
    def collect(self, request):
        return ConnectorBatch(
            connector_name="github",
            records_processed=2,
            items=[
                {
                    "kind": "pull_request",
                    "repository": "claston/micro-cardservice",
                    "number": 37,
                    "title": "docs: add marker",
                    "state": "closed",
                    "author": "alice",
                    "url": "https://github.com/claston/micro-cardservice/pull/37",
                    "source_key": "pull_request:37",
                },
                {
                    "kind": "commit",
                    "repository": "claston/micro-cardservice",
                    "sha": "f7079671bd93e410ff7270f9ac15b6cdd508f8a9",
                    "message": "docs(readme): add sync marker",
                    "author": "alice",
                    "committed_at": "2026-04-03T23:53:28Z",
                    "source_key": "commit:f7079671bd93e410ff7270f9ac15b6cdd508f8a9",
                },
            ],
            latest_cursor_by_target={"claston/micro-cardservice": "2026-04-03T23:58:54+00:00"},
        )


class ImmediateSyncJobDispatcher:
    def dispatch_sync(self, task, sync_run_id, connector_name, request):
        task(sync_run_id, connector_name, request)


def build_test_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    def override_get_sync_repository_scope():
        @contextmanager
        def scope():
            db = testing_session_local()
            try:
                yield SqlAlchemySyncRepository(db)
            finally:
                db.close()

        return scope

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_github_connector] = lambda: FakeGithubConnector()
    app.dependency_overrides[get_sync_job_dispatcher] = (
        lambda: ImmediateSyncJobDispatcher()
    )
    app.dependency_overrides[get_sync_repository_scope] = override_get_sync_repository_scope
    return TestClient(app)


def test_e2e_sync_normalize_and_mcp_tool_call() -> None:
    client = build_test_client()

    component = client.post(
        "/system-components",
        json={"name": "payment-api", "description": "payments"},
    )
    assert component.status_code == 200
    component_id = component.json()["id"]

    code_repo = client.post(
        "/code-repos",
        json={
            "system_component_id": component_id,
            "provider": "github",
            "name": "claston/micro-cardservice",
            "url": "https://github.com/claston/micro-cardservice",
            "default_branch": "main",
        },
    )
    assert code_repo.status_code == 200

    trigger = client.post(
        "/sync-runs/github",
        json={"system_component_name": "payment-api"},
    )
    assert trigger.status_code == 200
    sync_run_id = trigger.json()["id"]

    sync_run = client.get(f"/sync-runs/{sync_run_id}")
    assert sync_run.status_code == 200
    sync_payload = sync_run.json()
    assert sync_payload["status"] == "success"
    assert sync_payload["records_processed"] == 2

    normalize = client.post(f"/normalize/github/sync-runs/{sync_run_id}")
    assert normalize.status_code == 200
    normalize_payload = normalize.json()
    assert normalize_payload["raw_events_read"] == 2
    assert normalize_payload["errors"] == []
    assert (
        normalize_payload["pull_requests_created"]
        + normalize_payload["pull_requests_updated"]
    ) == 1
    assert (
        normalize_payload["commits_created"] + normalize_payload["commits_updated"]
    ) == 1

    mcp_call = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "mcp-e2e-1",
            "method": "tools/call",
            "params": {
                "name": "context.system_component.get",
                "arguments": {"name": "payment-api"},
            },
        },
    )
    assert mcp_call.status_code == 200
    mcp_payload = mcp_call.json()
    assert "error" not in mcp_payload

    context_payload = mcp_payload["result"]["content"][0]["json"]
    assert context_payload["system_component"] == "payment-api"
    assert context_payload["recent_pull_requests"] == 1
    assert context_payload["recent_commits"] == 1

    app.dependency_overrides.clear()
