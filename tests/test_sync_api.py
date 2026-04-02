from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application import SyncRunNotFoundError
from app.db import Base
from app.dependencies import get_sync_service
from app.main import app, get_db


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

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


class FakeSyncService:
    def __init__(self) -> None:
        self.item = {
            "id": str(uuid4()),
            "connector_name": "github",
            "status": "running",
            "records_processed": 0,
            "error_summary": None,
            "started_at": "2026-04-01T00:00:00Z",
            "finished_at": None,
            "created_at": "2026-04-01T00:00:00Z",
            "updated_at": "2026-04-01T00:00:00Z",
        }

    def trigger_github_sync(self, system_component_name: str | None = None):
        return self.item

    def get_sync_run(self, sync_run_id):
        if str(sync_run_id) != self.item["id"]:
            raise SyncRunNotFoundError("not found")
        return self.item


def test_post_sync_runs_github_returns_running() -> None:
    client = build_test_client()
    service = FakeSyncService()
    app.dependency_overrides[get_sync_service] = lambda: service
    response = client.post(
        "/sync-runs/github",
        json={"system_component_name": "payment-api"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["connector_name"] == "github"
    assert payload["status"] == "running"
    assert payload["records_processed"] == 0
    app.dependency_overrides.clear()


def test_get_sync_run_by_id_returns_payload() -> None:
    client = build_test_client()
    service = FakeSyncService()
    app.dependency_overrides[get_sync_service] = lambda: service

    response = client.get(f"/sync-runs/{service.item['id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == service.item["id"]
    assert payload["status"] == "running"
    app.dependency_overrides.clear()


def test_get_sync_run_by_id_returns_404_when_missing() -> None:
    client = build_test_client()
    service = FakeSyncService()
    app.dependency_overrides[get_sync_service] = lambda: service

    response = client.get(f"/sync-runs/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sync run not found"
    app.dependency_overrides.clear()
