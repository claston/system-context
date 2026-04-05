from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.connectors.base import ConnectorBatch
from app.db import Base
from app.dependencies import (
    get_db,
    get_mcp_api_token,
    get_render_runtime_connector,
    get_sync_job_dispatcher,
    get_sync_repository_scope,
)
from app.main import app
from app.repositories import SqlAlchemySyncRepository


class FakeRenderRuntimeConnector:
    def collect(self, request):
        return ConnectorBatch(
            connector_name="render-runtime",
            records_processed=1,
            items=[
                {
                    "kind": "runtime_snapshot",
                    "system_component_name": "micro-cardservice",
                    "environment": "staging",
                    "captured_at": "2026-04-05T12:00:00Z",
                    "instance_count": 2,
                    "health_status": "live",
                    "image_tag": "staging",
                    "service_id": "srv-123",
                    "source_key": "runtime_snapshot:dep-1",
                }
            ],
            latest_cursor_by_target={"srv-123": "2026-04-05T12:00:00+00:00"},
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
    app.dependency_overrides[get_mcp_api_token] = lambda: None
    app.dependency_overrides[get_render_runtime_connector] = (
        lambda: FakeRenderRuntimeConnector()
    )
    app.dependency_overrides[get_sync_job_dispatcher] = (
        lambda: ImmediateSyncJobDispatcher()
    )
    app.dependency_overrides[get_sync_repository_scope] = override_get_sync_repository_scope
    return TestClient(app)


def test_e2e_render_runtime_sync_populates_component_runtime_context() -> None:
    client = build_test_client()

    component = client.post(
        "/system-components",
        json={"name": "micro-cardservice", "description": "cards"},
    )
    assert component.status_code == 200

    trigger = client.post(
        "/sync-runs/render-runtime",
        json={"system_component_name": "micro-cardservice"},
    )
    assert trigger.status_code == 200
    sync_run_id = trigger.json()["id"]

    sync_run = client.get(f"/sync-runs/{sync_run_id}")
    assert sync_run.status_code == 200
    assert sync_run.json()["status"] == "success"
    assert sync_run.json()["records_processed"] == 1

    runtime = client.get(
        "/context/system-component/micro-cardservice/runtime",
        params={"environment": "staging"},
    )
    assert runtime.status_code == 200
    payload = runtime.json()
    assert payload["system_component"] == "micro-cardservice"
    assert payload["environment"] == "staging"
    assert payload["latest_runtime_health"] == "live"

    app.dependency_overrides.clear()
