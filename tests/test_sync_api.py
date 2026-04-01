from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
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


def test_post_sync_runs_github_returns_success() -> None:
    client = build_test_client()
    response = client.post(
        "/sync-runs/github",
        json={"system_component_name": "payment-api"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["connector_name"] == "github"
    assert payload["status"] == "success"
    assert payload["records_processed"] >= 1
    app.dependency_overrides.clear()
