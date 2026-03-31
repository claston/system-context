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


def test_entities_and_context_endpoints() -> None:
    client = build_test_client()

    system_component = client.post(
        "/system-components",
        json={"name": "payment-api", "description": "payments"},
    )
    assert system_component.status_code == 200
    sc_id = system_component.json()["id"]

    code_repo = client.post(
        "/code-repos",
        json={
            "system_component_id": sc_id,
            "provider": "github",
            "name": "payment-api",
            "url": "https://github.com/org/payment-api",
            "default_branch": "main",
        },
    )
    assert code_repo.status_code == 200
    repo_id = code_repo.json()["id"]

    pull_request = client.post(
        "/pull-requests",
        json={
            "code_repo_id": repo_id,
            "number": "123",
            "title": "feat: add payment endpoint",
            "status": "open",
        },
    )
    assert pull_request.status_code == 200

    commit = client.post(
        "/commits",
        json={
            "code_repo_id": repo_id,
            "sha": "abc123",
            "message": "add payment endpoint",
        },
    )
    assert commit.status_code == 200

    deployment = client.post(
        "/deployments",
        json={
            "system_component_id": sc_id,
            "environment": "prod",
            "version": "1.0.0",
            "status": "success",
        },
    )
    assert deployment.status_code == 200

    runtime_snapshot = client.post(
        "/runtime-snapshots",
        json={
            "system_component_id": sc_id,
            "environment": "prod",
            "health_status": "healthy",
            "pod_count": "3",
            "restart_count": "0",
        },
    )
    assert runtime_snapshot.status_code == 200

    dependency_target = client.post(
        "/system-components",
        json={"name": "ledger-api", "description": "ledger"},
    )
    assert dependency_target.status_code == 200
    target_id = dependency_target.json()["id"]

    dependency = client.post(
        "/dependencies",
        json={
            "source_system_component_id": sc_id,
            "target_system_component_id": target_id,
            "dependency_type": "http",
        },
    )
    assert dependency.status_code == 200

    context_main = client.get("/context/system-component/payment-api")
    assert context_main.status_code == 200
    assert context_main.json()["system_component"] == "payment-api"
    assert context_main.json()["recent_pull_requests"] == 1
    assert context_main.json()["recent_commits"] == 1

    context_changes = client.get("/context/system-component/payment-api/changes")
    assert context_changes.status_code == 200

    context_runtime = client.get("/context/system-component/payment-api/runtime")
    assert context_runtime.status_code == 200
    assert context_runtime.json()["latest_runtime_health"] == "healthy"

    context_dependencies = client.get("/context/system-component/payment-api/dependencies")
    assert context_dependencies.status_code == 200
    assert len(context_dependencies.json()["dependencies"]) == 1

    system_state = client.get("/context/system/current-state")
    assert system_state.status_code == 200

    agent_context = client.post(
        "/agent/context",
        json={"system_component_name": "payment-api", "environment": "prod"},
    )
    assert agent_context.status_code == 200

    app.dependency_overrides.clear()
