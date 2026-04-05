from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.dependencies import (
    get_context_service,
    get_mcp_api_token,
    get_mcp_tool_timeout_seconds,
)
from app.main import app, get_db


def _build_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _assert_mcp_success(response, request_id: str):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == request_id
    assert "error" not in payload, payload
    return payload


def _build_auth_headers() -> dict[str, str]:
    token = get_mcp_api_token()
    if not token:
        return {}
    return {"X-MCP-API-Key": token}


def run_smoke_checks() -> None:
    client = _build_client()
    auth_headers = _build_auth_headers()
    try:
        initialize = client.post(
            "/mcp",
            headers=auth_headers,
            json={
                "jsonrpc": "2.0",
                "id": "init-smoke",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "clientInfo": {"name": "ci-smoke", "version": "0.1"},
                },
            },
        )
        init_payload = _assert_mcp_success(initialize, "init-smoke")
        assert init_payload["result"]["serverInfo"]["name"] == "system-context-mcp"

        tools_list = client.post(
            "/mcp",
            headers=auth_headers,
            json={
                "jsonrpc": "2.0",
                "id": "tools-smoke",
                "method": "tools/list",
                "params": {},
            },
        )
        tools_payload = _assert_mcp_success(tools_list, "tools-smoke")
        tool_names = [item["name"] for item in tools_payload["result"]["tools"]]
        assert "context.system.current_state" in tool_names
        assert "context.system_component.get" in tool_names

        created_component = client.post(
            "/system-components",
            json={"name": "payment-api", "description": "smoke"},
        )
        assert created_component.status_code == 200, created_component.text

        current_state = client.post(
            "/mcp",
            headers=auth_headers,
            json={
                "jsonrpc": "2.0",
                "id": "current-state-smoke",
                "method": "tools/call",
                "params": {
                    "name": "context.system.current_state",
                    "arguments": {},
                },
            },
        )
        current_state_payload = _assert_mcp_success(
            current_state, "current-state-smoke"
        )
        assert (
            current_state_payload["result"]["content"][0]["json"][
                "system_component_count"
            ]
            == 1
        )

        app.dependency_overrides[get_mcp_api_token] = lambda: "top-secret"
        unauthorized = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "auth-missing",
                "method": "tools/list",
                "params": {},
            },
        )
        assert unauthorized.status_code == 401
        unauthorized_payload = unauthorized.json()
        assert unauthorized_payload["error"]["code"] == -32001

        authorized = client.post(
            "/mcp",
            headers={"X-MCP-API-Key": "top-secret"},
            json={
                "jsonrpc": "2.0",
                "id": "auth-ok",
                "method": "tools/list",
                "params": {},
            },
        )
        _assert_mcp_success(authorized, "auth-ok")

        class SlowContextService:
            def get_system_current_state(self):
                time.sleep(0.05)
                return {"system_component_count": 0}

        app.dependency_overrides[get_mcp_tool_timeout_seconds] = lambda: 0.001
        app.dependency_overrides[get_context_service] = lambda: SlowContextService()

        timeout_response = client.post(
            "/mcp",
            headers={"X-MCP-API-Key": "top-secret"},
            json={
                "jsonrpc": "2.0",
                "id": "timeout-smoke",
                "method": "tools/call",
                "params": {
                    "name": "context.system.current_state",
                    "arguments": {},
                },
            },
        )
        assert timeout_response.status_code == 200
        timeout_payload = timeout_response.json()
        assert timeout_payload["error"]["code"] == -32008
        assert timeout_payload["error"]["data"]["request_id"] == "timeout-smoke"

        print("MCP smoke checks passed")
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    run_smoke_checks()
