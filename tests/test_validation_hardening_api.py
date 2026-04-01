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


def test_create_system_component_with_blank_name_returns_400() -> None:
    client = build_test_client()
    response = client.post(
        "/system-components",
        json={"name": "   ", "description": "desc"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Validation failed"
    app.dependency_overrides.clear()


def test_create_code_repo_with_invalid_provider_and_url_returns_400() -> None:
    client = build_test_client()
    system_component = client.post(
        "/system-components",
        json={"name": "payment-api", "description": "payments"},
    )
    sc_id = system_component.json()["id"]

    response = client.post(
        "/code-repos",
        json={
            "system_component_id": sc_id,
            "provider": "svn",
            "name": "payment-api",
            "url": "not-a-url",
            "default_branch": "main",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Validation failed"
    app.dependency_overrides.clear()


def test_create_deployment_with_invalid_status_returns_400() -> None:
    client = build_test_client()
    system_component = client.post(
        "/system-components",
        json={"name": "billing-api", "description": "billing"},
    )
    sc_id = system_component.json()["id"]

    response = client.post(
        "/deployments",
        json={
            "system_component_id": sc_id,
            "environment": "prod",
            "version": "1.0.0",
            "status": "unknown",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Validation failed"
    app.dependency_overrides.clear()


def test_create_duplicate_pull_request_returns_409() -> None:
    client = build_test_client()
    system_component = client.post(
        "/system-components",
        json={"name": "checkout-api", "description": "checkout"},
    )
    sc_id = system_component.json()["id"]

    code_repo = client.post(
        "/code-repos",
        json={
            "system_component_id": sc_id,
            "provider": "github",
            "name": "checkout-api",
            "url": "https://github.com/org/checkout-api",
            "default_branch": "main",
        },
    )
    repo_id = code_repo.json()["id"]

    first = client.post(
        "/pull-requests",
        json={
            "code_repo_id": repo_id,
            "number": "42",
            "title": "feat: checkout",
            "status": "open",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/pull-requests",
        json={
            "code_repo_id": repo_id,
            "number": "42",
            "title": "feat: checkout duplicate",
            "status": "open",
        },
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Resource already exists"
    app.dependency_overrides.clear()


def test_create_runtime_snapshot_with_non_integer_counts_returns_400() -> None:
    client = build_test_client()
    system_component = client.post(
        "/system-components",
        json={"name": "runtime-api", "description": "runtime"},
    )
    sc_id = system_component.json()["id"]

    response = client.post(
        "/runtime-snapshots",
        json={
            "system_component_id": sc_id,
            "environment": "prod",
            "pod_count": "three",
            "restart_count": "zero",
            "health_status": "healthy",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Validation failed"
    app.dependency_overrides.clear()


def test_create_sync_run_with_non_integer_records_processed_returns_400() -> None:
    client = build_test_client()
    response = client.post(
        "/sync-runs",
        json={
            "connector_name": "github",
            "status": "success",
            "records_processed": "many",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Validation failed"
    app.dependency_overrides.clear()


def test_create_sync_run_with_finished_before_started_returns_400() -> None:
    client = build_test_client()
    response = client.post(
        "/sync-runs",
        json={
            "connector_name": "github",
            "status": "success",
            "records_processed": 10,
            "started_at": "2026-03-31T10:00:00Z",
            "finished_at": "2026-03-31T09:00:00Z",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Validation failed"
    app.dependency_overrides.clear()
