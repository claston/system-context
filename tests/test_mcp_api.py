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


def test_mcp_initialize_returns_server_capabilities() -> None:
    client = build_test_client()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "clientInfo": {"name": "pytest", "version": "0.1"},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == "init-1"
    assert payload["result"]["serverInfo"]["name"] == "system-context-mcp"
    assert payload["result"]["capabilities"]["tools"] == {}
    app.dependency_overrides.clear()


def test_mcp_tools_list_returns_core_context_tools() -> None:
    client = build_test_client()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "tools-1",
            "method": "tools/list",
            "params": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    names = [item["name"] for item in payload["result"]["tools"]]
    assert "context.system.current_state" in names
    assert "context.system_component.get" in names
    assert "context.system_component.changes" in names
    assert "context.system_component.runtime" in names
    assert "context.system_component.dependencies" in names
    app.dependency_overrides.clear()


def test_mcp_tools_call_current_state_returns_json_payload() -> None:
    client = build_test_client()

    create_component = client.post(
        "/system-components",
        json={"name": "payment-api", "description": "payments"},
    )
    assert create_component.status_code == 200

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {
                "name": "context.system.current_state",
                "arguments": {},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["content"][0]["type"] == "json"
    result_json = payload["result"]["content"][0]["json"]
    assert result_json["system_component_count"] == 1
    app.dependency_overrides.clear()


def test_mcp_tools_call_returns_jsonrpc_error_for_missing_component() -> None:
    client = build_test_client()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "call-2",
            "method": "tools/call",
            "params": {
                "name": "context.system_component.get",
                "arguments": {"name": "missing-component"},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"]["code"] == -32004
    assert payload["error"]["message"] == "System component not found"
    app.dependency_overrides.clear()
