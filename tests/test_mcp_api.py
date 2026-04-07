import json
import logging

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.dependencies import (
    get_context_service,
    get_mcp_api_token,
    get_mcp_audit_log_enabled,
    get_mcp_audit_log_include_result_body,
    get_mcp_audit_log_max_payload_chars,
    get_mcp_tool_timeout_seconds,
    get_render_logs_analysis_service,
)
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
    app.dependency_overrides[get_mcp_api_token] = lambda: None
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
    assert "context.system_component.errors_analyze" in names
    app.dependency_overrides.clear()


def test_mcp_resources_list_returns_discovery_resources() -> None:
    client = build_test_client()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "resources-1",
            "method": "resources/list",
            "params": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    resources = payload["result"]["resources"]
    uris = [item["uri"] for item in resources]
    assert "context://system/components" in uris
    assert "context://system/environments" in uris
    app.dependency_overrides.clear()


def test_mcp_resource_templates_list_returns_component_template() -> None:
    client = build_test_client()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "resource-templates-1",
            "method": "resources/templates/list",
            "params": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    template_uris = [
        item["uriTemplate"] for item in payload["result"]["resourceTemplates"]
    ]
    assert "context://system/component/{name}" in template_uris
    app.dependency_overrides.clear()


def test_mcp_initialized_notification_without_id_is_accepted() -> None:
    client = build_test_client()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
    )

    assert response.status_code == 204
    assert response.content == b""
    app.dependency_overrides.clear()


def test_mcp_initialized_with_id_returns_success_payload() -> None:
    client = build_test_client()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "initialized-1",
            "method": "notifications/initialized",
            "params": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == "initialized-1"
    assert payload["result"] == {}
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
    assert payload["result"]["content"][0]["type"] == "text"
    content_as_json = json.loads(payload["result"]["content"][0]["text"])
    assert content_as_json["system_component_count"] == 1
    assert payload["result"]["structuredContent"]["system_component_count"] == 1
    app.dependency_overrides.clear()


def test_mcp_resources_read_component_list_returns_json_text() -> None:
    client = build_test_client()
    create_component = client.post(
        "/system-components",
        json={"name": "micro-cardservice", "description": "card"},
    )
    assert create_component.status_code == 200

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "resources-read-1",
            "method": "resources/read",
            "params": {"uri": "context://system/components"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["contents"][0]["mimeType"] == "application/json"
    data = json.loads(payload["result"]["contents"][0]["text"])
    assert "micro-cardservice" in data["components"]
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


def test_mcp_returns_401_when_auth_is_required_and_header_is_missing() -> None:
    client = build_test_client()
    app.dependency_overrides[get_mcp_api_token] = lambda: "top-secret"

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "auth-1",
            "method": "initialize",
            "params": {},
        },
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == "auth-1"
    assert payload["error"]["code"] == -32001
    assert payload["error"]["message"] == "Unauthorized"
    app.dependency_overrides.clear()


def test_mcp_accepts_call_when_auth_header_matches() -> None:
    client = build_test_client()
    app.dependency_overrides[get_mcp_api_token] = lambda: "top-secret"

    response = client.post(
        "/mcp",
        headers={"X-MCP-API-Key": "top-secret"},
        json={
            "jsonrpc": "2.0",
            "id": "auth-2",
            "method": "tools/list",
            "params": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "result" in payload
    assert payload["result"]["tools"]
    app.dependency_overrides.clear()


def test_mcp_invalid_request_includes_request_id_in_error_data() -> None:
    client = build_test_client()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "invalid-1",
            "params": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"]["code"] == -32600
    assert payload["error"]["message"] == "Invalid Request"
    assert payload["error"]["data"]["request_id"] == "invalid-1"
    app.dependency_overrides.clear()


def test_mcp_tool_timeout_returns_jsonrpc_error() -> None:
    class SlowContextService:
        def get_system_current_state(self):
            import time

            time.sleep(0.05)
            return {"system_component_count": 0}

    client = build_test_client()
    app.dependency_overrides[get_mcp_tool_timeout_seconds] = lambda: 0.001
    app.dependency_overrides[get_context_service] = lambda: SlowContextService()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "timeout-1",
            "method": "tools/call",
            "params": {
                "name": "context.system.current_state",
                "arguments": {},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"]["code"] == -32008
    assert payload["error"]["message"] == "Tool execution timeout"
    assert payload["error"]["data"]["request_id"] == "timeout-1"
    app.dependency_overrides.clear()


def test_mcp_tools_call_returns_jsonrpc_error_for_database_operational_error() -> None:
    class FailingContextService:
        def get_system_current_state(self):
            raise OperationalError("SELECT 1", {}, Exception("connection dropped"))

    client = build_test_client()
    app.dependency_overrides[get_context_service] = lambda: FailingContextService()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "db-1",
            "method": "tools/call",
            "params": {
                "name": "context.system.current_state",
                "arguments": {},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"]["code"] == -32010
    assert payload["error"]["message"] == "Database temporarily unavailable"
    assert payload["error"]["data"]["request_id"] == "db-1"
    app.dependency_overrides.clear()


def test_mcp_tools_call_errors_analyze_returns_json_payload() -> None:
    class FakeRenderLogsAnalysisService:
        def analyze_recent_errors(self, component_name, *, minutes, limit, environment=None):
            return {
                "system_component": component_name,
                "service_id": "srv-123",
                "environment": environment or "staging",
                "window": {"minutes": minutes},
                "error_event_count": 2,
                "top_issues": [
                    {
                        "signature": "error timeout calling db",
                        "count": 2,
                        "severity": "high",
                        "sample_message": "ERROR timeout calling db request_id=123",
                        "affected_sources": ["web"],
                    }
                ],
                "likely_causes": ["Dependency timeout"],
                "suggested_actions": ["Check DB latency and retry policy."],
                "sample_log_lines": ["ERROR timeout calling db request_id=123"],
            }

    client = build_test_client()
    app.dependency_overrides[get_render_logs_analysis_service] = (
        lambda: FakeRenderLogsAnalysisService()
    )

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "errors-1",
            "method": "tools/call",
            "params": {
                "name": "context.system_component.errors_analyze",
                "arguments": {"name": "micro-cardservice", "minutes": 30, "limit": 200},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["content"][0]["type"] == "text"
    content_as_json = json.loads(payload["result"]["content"][0]["text"])
    assert content_as_json["system_component"] == "micro-cardservice"
    assert content_as_json["error_event_count"] == 2
    assert content_as_json["top_issues"][0]["severity"] == "high"
    assert payload["result"]["structuredContent"]["system_component"] == "micro-cardservice"
    assert payload["result"]["structuredContent"]["error_event_count"] == 2
    app.dependency_overrides.clear()


def test_mcp_audit_log_records_request_and_result(caplog) -> None:
    client = build_test_client()
    app.dependency_overrides[get_mcp_audit_log_enabled] = lambda: True
    app.dependency_overrides[get_mcp_audit_log_include_result_body] = lambda: True
    app.dependency_overrides[get_mcp_audit_log_max_payload_chars] = lambda: 2_000

    with caplog.at_level(logging.INFO, logger="app.mcp.audit"):
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "audit-1",
                "method": "tools/call",
                "params": {
                    "name": "context.system.current_state",
                    "arguments": {},
                },
            },
        )

    assert response.status_code == 200
    events = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "app.mcp.audit"
    ]
    event_names = [event["event"] for event in events]
    assert "mcp.request.received" in event_names
    assert "mcp.tool.call.start" in event_names
    assert "mcp.tool.call.success" in event_names
    assert "mcp.request.completed" in event_names

    success_event = next(event for event in events if event["event"] == "mcp.tool.call.success")
    assert success_event["request_id"] == "audit-1"
    assert success_event["tool_name"] == "context.system.current_state"
    assert "result_preview" in success_event
    app.dependency_overrides.clear()


def test_mcp_audit_log_redacts_auth_and_truncates_payload(caplog) -> None:
    client = build_test_client()
    app.dependency_overrides[get_mcp_audit_log_enabled] = lambda: True
    app.dependency_overrides[get_mcp_audit_log_include_result_body] = lambda: False
    app.dependency_overrides[get_mcp_audit_log_max_payload_chars] = lambda: 40

    with caplog.at_level(logging.INFO, logger="app.mcp.audit"):
        response = client.post(
            "/mcp",
            headers={"Authorization": "Bearer top-secret-token"},
            json={
                "jsonrpc": "2.0",
                "id": "audit-2",
                "method": "initialize",
                "params": {"clientInfo": {"name": "x" * 200}},
            },
        )

    assert response.status_code == 200
    events = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "app.mcp.audit"
    ]
    received_event = next(event for event in events if event["event"] == "mcp.request.received")
    assert received_event["auth"]["authorization"] == "***"
    assert received_event["params_truncated"] is True
    assert received_event["params_preview"].endswith("...")
    assert "top-secret-token" not in json.dumps(events)
    app.dependency_overrides.clear()
