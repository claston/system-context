from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.dependencies import get_db
from app.main import app


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


def test_integration_target_mapping_create_list_get_and_patch() -> None:
    client = build_test_client()

    component = client.post(
        "/system-components",
        json={"name": "micro-cardservice", "description": "cards"},
    )
    assert component.status_code == 200
    component_id = component.json()["id"]

    create = client.post(
        "/integration-target-mappings",
        json={
            "connector_name": "render-runtime",
            "external_target_id": "srv-123",
            "external_target_name": "cardservice-staging",
            "system_component_id": component_id,
            "environment": "staging",
            "metadata": {"region": "oregon"},
            "is_active": True,
        },
    )
    assert create.status_code == 201
    created = create.json()
    assert created["connector_name"] == "render-runtime"
    assert created["external_target_id"] == "srv-123"
    assert created["external_target_name"] == "cardservice-staging"
    assert created["system_component_id"] == component_id
    assert created["environment"] == "staging"
    assert created["metadata"] == {"region": "oregon"}
    assert created["is_active"] is True
    mapping_id = created["id"]

    listed = client.get("/integration-target-mappings")
    assert listed.status_code == 200
    list_payload = listed.json()
    assert len(list_payload) == 1
    assert list_payload[0]["id"] == mapping_id

    listed_filtered = client.get(
        "/integration-target-mappings",
        params={"connector_name": "render-runtime", "environment": "staging"},
    )
    assert listed_filtered.status_code == 200
    assert len(listed_filtered.json()) == 1

    fetched = client.get(f"/integration-target-mappings/{mapping_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == mapping_id

    patched = client.patch(
        f"/integration-target-mappings/{mapping_id}",
        json={
            "external_target_name": "cardservice-updated",
            "is_active": False,
            "metadata": {"region": "virginia"},
        },
    )
    assert patched.status_code == 200
    assert patched.json()["external_target_name"] == "cardservice-updated"
    assert patched.json()["is_active"] is False
    assert patched.json()["metadata"] == {"region": "virginia"}

    app.dependency_overrides.clear()


def test_integration_target_mapping_api_errors() -> None:
    client = build_test_client()

    component = client.post(
        "/system-components",
        json={"name": "micro-ledger", "description": "ledger"},
    )
    assert component.status_code == 200
    component_id = component.json()["id"]

    first = client.post(
        "/integration-target-mappings",
        json={
            "connector_name": "render-runtime",
            "external_target_id": "srv-456",
            "system_component_id": component_id,
            "environment": "staging",
        },
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/integration-target-mappings",
        json={
            "connector_name": "render-runtime",
            "external_target_id": "srv-456",
            "system_component_id": component_id,
            "environment": "staging",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Integration target mapping already exists"

    invalid_component = client.post(
        "/integration-target-mappings",
        json={
            "connector_name": "render-runtime",
            "external_target_id": "srv-789",
            "system_component_id": "00000000-0000-0000-0000-000000000000",
            "environment": "staging",
        },
    )
    assert invalid_component.status_code == 404
    assert invalid_component.json()["detail"] == "System component not found"

    missing = client.get(
        "/integration-target-mappings/00000000-0000-0000-0000-000000000000"
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Integration target mapping not found"

    app.dependency_overrides.clear()
