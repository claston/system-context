from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application import (
    NormalizationSyncRunNotFoundError,
    UnsupportedNormalizationConnectorError,
)
from app.db import Base
from app.dependencies import get_github_normalization_service
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


class FakeGithubNormalizationService:
    def __init__(self) -> None:
        self.response = {
            "sync_run_id": str(uuid4()),
            "connector_name": "github",
            "raw_events_read": 2,
            "pull_requests_created": 1,
            "pull_requests_updated": 0,
            "commits_created": 1,
            "commits_updated": 0,
            "skipped": 0,
            "errors": [],
        }

    def normalize_sync_run(self, sync_run_id):
        if str(sync_run_id) == "00000000-0000-0000-0000-000000000000":
            raise NormalizationSyncRunNotFoundError("not found")
        if str(sync_run_id) == "11111111-1111-1111-1111-111111111111":
            raise UnsupportedNormalizationConnectorError("unsupported connector")
        self.response["sync_run_id"] = str(sync_run_id)
        return self.response


def test_post_normalize_github_sync_run_returns_summary() -> None:
    client = build_test_client()
    service = FakeGithubNormalizationService()
    app.dependency_overrides[get_github_normalization_service] = lambda: service
    sync_run_id = str(uuid4())

    response = client.post(f"/normalize/github/sync-runs/{sync_run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sync_run_id"] == sync_run_id
    assert payload["pull_requests_created"] == 1
    assert payload["commits_created"] == 1
    app.dependency_overrides.clear()


def test_post_normalize_github_sync_run_returns_404_when_sync_run_missing() -> None:
    client = build_test_client()
    service = FakeGithubNormalizationService()
    app.dependency_overrides[get_github_normalization_service] = lambda: service

    response = client.post(
        "/normalize/github/sync-runs/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Sync run not found"
    app.dependency_overrides.clear()


def test_post_normalize_github_sync_run_returns_400_for_unsupported_connector() -> None:
    client = build_test_client()
    service = FakeGithubNormalizationService()
    app.dependency_overrides[get_github_normalization_service] = lambda: service

    response = client.post(
        "/normalize/github/sync-runs/11111111-1111-1111-1111-111111111111"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported connector"
    app.dependency_overrides.clear()
