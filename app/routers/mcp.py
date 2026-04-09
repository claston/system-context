import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.application import ContextService, SystemComponentNotFoundError
from app.dependencies import (
    get_context_service,
    get_mcp_api_token,
    get_mcp_audit_log_enabled,
    get_mcp_audit_log_include_result_body,
    get_mcp_audit_log_max_payload_chars,
    get_mcp_tool_timeout_seconds,
    get_render_logs_analysis_service,
)
from app.observability import emit_mcp_audit_event

router = APIRouter()


TOOLS: list[dict[str, Any]] = [
    {
        "name": "context.system.current_state",
        "description": "Return aggregate system counts.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "context.system_component.get",
        "description": "Return full context for a system component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "environment": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "context.system_component.changes",
        "description": "Return recent PR and commit counters for a component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "context.system_component.runtime",
        "description": "Return latest runtime and deployment summary for a component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "environment": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "context.system_component.dependencies",
        "description": "Return dependency list for a component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "context.system_component.errors_analyze",
        "description": "Analyze recent Render error logs for a system component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "environment": {"type": "string"},
                "minutes": {"type": "integer", "minimum": 1, "maximum": 180},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
]

RESOURCES: list[dict[str, Any]] = [
    {
        "uri": "context://system/components",
        "name": "System Components",
        "description": "List valid system component names.",
        "mimeType": "application/json",
    },
    {
        "uri": "context://system/environments",
        "name": "Environments",
        "description": "List known deployment/runtime environments.",
        "mimeType": "application/json",
    },
]

RESOURCE_TEMPLATES: list[dict[str, Any]] = [
    {
        "uriTemplate": "context://system/component/{name}",
        "name": "System Component Context",
        "description": "Read full context for a specific system component.",
        "mimeType": "application/json",
    }
]


def _jsonrpc_success(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def _jsonrpc_error(
    request_id: Any,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error_data: dict[str, Any] = {"request_id": request_id}
    if data is not None:
        error_data.update(data)
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
            "data": error_data,
        },
    }
    return payload


def _read_required_component_name(arguments: dict[str, Any]) -> str:
    name = str(arguments.get("name") or "").strip()
    if not name:
        raise ValueError("argument 'name' is required")
    return name


def _tool_result(json_payload: dict[str, Any]) -> dict[str, Any]:
    text_payload = json.dumps(
        json_payload,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "structuredContent": json_payload,
        "content": [
            {
                "type": "text",
                "text": text_payload,
            }
        ]
    }


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    raw_value = authorization.strip()
    if not raw_value.lower().startswith("bearer "):
        return None
    token = raw_value[7:].strip()
    return token or None


def _execute_with_timeout(tool_call, timeout_seconds: float):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(tool_call)
        return future.result(timeout=max(0.001, timeout_seconds))


def _resource_read_result(uri: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(payload, separators=(",", ":"), sort_keys=True),
            }
        ]
    }


@router.post("/mcp")
def handle_mcp_request(
    payload: dict[str, Any],
    context_service: ContextService = Depends(get_context_service),
    render_logs_analysis_service=Depends(get_render_logs_analysis_service),
    mcp_api_token: str | None = Depends(get_mcp_api_token),
    mcp_tool_timeout_seconds: float = Depends(get_mcp_tool_timeout_seconds),
    mcp_audit_log_enabled: bool = Depends(get_mcp_audit_log_enabled),
    mcp_audit_log_include_result_body: bool = Depends(get_mcp_audit_log_include_result_body),
    mcp_audit_log_max_payload_chars: int = Depends(get_mcp_audit_log_max_payload_chars),
    mcp_header_token: str | None = Header(default=None, alias="X-MCP-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params")
    request_started = time.perf_counter()
    trace_id = str(request_id) if request_id is not None else f"mcp-{uuid4().hex[:12]}"

    def audit(event: str, **kwargs: Any) -> None:
        if not mcp_audit_log_enabled:
            return
        emit_mcp_audit_event(
            event,
            trace_id=trace_id,
            request_id=request_id,
            method=method if isinstance(method, str) else None,
            max_payload_chars=mcp_audit_log_max_payload_chars,
            include_result_body=mcp_audit_log_include_result_body,
            **kwargs,
        )

    def complete(outcome: str, error_code: int | None = None, error_message: str | None = None) -> None:
        audit(
            "mcp.request.completed",
            duration_ms=(time.perf_counter() - request_started) * 1000,
            outcome=outcome,
            error_code=error_code,
            error_message=error_message,
        )

    audit(
        "mcp.request.received",
        params=params,
        auth={"authorization": authorization, "x-mcp-api-key": mcp_header_token},
    )

    if mcp_api_token is not None:
        bearer_token = _extract_bearer_token(authorization)
        provided_token = mcp_header_token or bearer_token
        if provided_token != mcp_api_token:
            complete("error", error_code=-32001, error_message="Unauthorized")
            return JSONResponse(
                status_code=401,
                content=_jsonrpc_error(request_id, -32001, "Unauthorized"),
            )

    if payload.get("jsonrpc") != "2.0":
        complete("error", error_code=-32600, error_message="Invalid Request")
        return _jsonrpc_error(request_id, -32600, "Invalid Request")

    if not isinstance(method, str) or not method.strip():
        complete("error", error_code=-32600, error_message="Invalid Request")
        return _jsonrpc_error(request_id, -32600, "Invalid Request")
    params = params or {}
    if not isinstance(params, dict):
        complete("error", error_code=-32602, error_message="Invalid params")
        return _jsonrpc_error(request_id, -32602, "Invalid params")

    if method == "initialize":
        protocol_version = str(params.get("protocolVersion") or "2025-03-26")
        response_payload = _jsonrpc_success(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
                "serverInfo": {
                    "name": "system-context-mcp",
                    "version": "0.1.0",
                },
            },
        )
        complete("success")
        return response_payload

    if method == "notifications/initialized":
        if request_id is None:
            complete("success")
            return Response(status_code=204)
        complete("success")
        return _jsonrpc_success(request_id, {})

    if method == "tools/list":
        complete("success")
        return _jsonrpc_success(request_id, {"tools": TOOLS})

    if method == "resources/list":
        complete("success")
        return _jsonrpc_success(request_id, {"resources": RESOURCES})

    if method == "resources/templates/list":
        complete("success")
        return _jsonrpc_success(
            request_id,
            {"resourceTemplates": RESOURCE_TEMPLATES},
        )

    if method == "resources/read":
        uri = str(params.get("uri") or "").strip()
        if not uri:
            complete("error", error_code=-32602, error_message="Invalid params")
            return _jsonrpc_error(
                request_id,
                -32602,
                "Invalid params",
                {"detail": "parameter 'uri' is required"},
            )

        try:
            if uri == "context://system/components":
                complete("success")
                return _jsonrpc_success(
                    request_id,
                    _resource_read_result(
                        uri,
                        {"components": context_service.list_system_component_names()},
                    ),
                )

            if uri == "context://system/environments":
                complete("success")
                return _jsonrpc_success(
                    request_id,
                    _resource_read_result(
                        uri,
                        {"environments": context_service.list_known_environments()},
                    ),
                )

            component_prefix = "context://system/component/"
            if uri.startswith(component_prefix):
                component_name = uri.removeprefix(component_prefix).strip()
                if not component_name:
                    return _jsonrpc_error(
                        request_id,
                        -32602,
                        "Invalid params",
                        {"detail": "resource uri must include component name"},
                    )
                environment = params.get("environment")
                if environment is not None:
                    environment = str(environment).strip() or None
                complete("success")
                return _jsonrpc_success(
                    request_id,
                    _resource_read_result(
                        uri,
                        context_service.get_system_component_context(
                            component_name,
                            environment,
                        ),
                    ),
                )
        except SystemComponentNotFoundError:
            complete("error", error_code=-32004, error_message="System component not found")
            return _jsonrpc_error(request_id, -32004, "System component not found")

        complete("error", error_code=-32004, error_message="Resource not found")
        return _jsonrpc_error(request_id, -32004, "Resource not found")

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(tool_name, str) or not tool_name.strip():
            complete("error", error_code=-32602, error_message="Invalid params")
            return _jsonrpc_error(request_id, -32602, "Invalid params")
        if not isinstance(arguments, dict):
            complete("error", error_code=-32602, error_message="Invalid params")
            return _jsonrpc_error(request_id, -32602, "Invalid params")

        tool_started = time.perf_counter()
        audit("mcp.tool.call.start", tool_name=tool_name, arguments=arguments)

        def run_tool():
            if tool_name == "context.system.current_state":
                return _tool_result(context_service.get_system_current_state())

            if tool_name == "context.system_component.get":
                component_name = _read_required_component_name(arguments)
                environment = arguments.get("environment")
                if environment is not None:
                    environment = str(environment).strip() or None
                return _tool_result(
                    context_service.get_system_component_context(
                        component_name,
                        environment,
                    )
                )

            if tool_name == "context.system_component.changes":
                component_name = _read_required_component_name(arguments)
                context = context_service.get_system_component_context(component_name)
                return _tool_result(
                    {
                        "system_component": context["system_component"],
                        "recent_pull_requests": context["recent_pull_requests"],
                        "recent_commits": context["recent_commits"],
                    }
                )

            if tool_name == "context.system_component.runtime":
                component_name = _read_required_component_name(arguments)
                environment = arguments.get("environment")
                if environment is not None:
                    environment = str(environment).strip() or None
                context = context_service.get_system_component_context(
                    component_name,
                    environment,
                )
                return _tool_result(
                    {
                        "system_component": context["system_component"],
                        "environment": context["environment"],
                        "latest_runtime_health": context["latest_runtime_health"],
                        "latest_deployment_version": context[
                            "latest_deployment_version"
                        ],
                        "app_up": context["app_up"],
                        "open_operational_issues": context["open_operational_issues"],
                        "unexpected_restarts_last_24h": context[
                            "unexpected_restarts_last_24h"
                        ],
                        "last_unexpected_restart_at": context[
                            "last_unexpected_restart_at"
                        ],
                    }
                )

            if tool_name == "context.system_component.dependencies":
                component_name = _read_required_component_name(arguments)
                context = context_service.get_system_component_context(component_name)
                return _tool_result(
                    {
                        "system_component": context["system_component"],
                        "dependencies": context["dependencies"],
                    }
                )

            if tool_name == "context.system_component.errors_analyze":
                component_name = _read_required_component_name(arguments)
                environment = arguments.get("environment")
                if environment is not None:
                    environment = str(environment).strip() or None
                minutes = int(arguments.get("minutes") or 30)
                limit = int(arguments.get("limit") or 300)
                return _tool_result(
                    render_logs_analysis_service.analyze_recent_errors(
                        component_name,
                        minutes=minutes,
                        limit=limit,
                        environment=environment,
                    )
                )

            return None

        try:
            tool_result = _execute_with_timeout(run_tool, mcp_tool_timeout_seconds)
            if tool_result is None:
                audit(
                    "mcp.tool.call.error",
                    tool_name=tool_name,
                    arguments=arguments,
                    duration_ms=(time.perf_counter() - tool_started) * 1000,
                    error_code=-32601,
                    error_message="Method not found",
                )
                complete("error", error_code=-32601, error_message="Method not found")
                return _jsonrpc_error(request_id, -32601, "Method not found")
            audit(
                "mcp.tool.call.success",
                tool_name=tool_name,
                arguments=arguments,
                result=tool_result,
                duration_ms=(time.perf_counter() - tool_started) * 1000,
            )
            complete("success")
            return _jsonrpc_success(request_id, tool_result)
        except ValueError as exc:
            audit(
                "mcp.tool.call.error",
                tool_name=tool_name,
                arguments=arguments,
                duration_ms=(time.perf_counter() - tool_started) * 1000,
                error_code=-32602,
                error_message=str(exc),
            )
            complete("error", error_code=-32602, error_message="Invalid params")
            return _jsonrpc_error(request_id, -32602, "Invalid params", {"detail": str(exc)})
        except FuturesTimeoutError:
            audit(
                "mcp.tool.call.error",
                tool_name=tool_name,
                arguments=arguments,
                duration_ms=(time.perf_counter() - tool_started) * 1000,
                error_code=-32008,
                error_message="Tool execution timeout",
            )
            complete("error", error_code=-32008, error_message="Tool execution timeout")
            return _jsonrpc_error(request_id, -32008, "Tool execution timeout")
        except OperationalError:
            audit(
                "mcp.tool.call.error",
                tool_name=tool_name,
                arguments=arguments,
                duration_ms=(time.perf_counter() - tool_started) * 1000,
                error_code=-32010,
                error_message="Database temporarily unavailable",
            )
            complete("error", error_code=-32010, error_message="Database temporarily unavailable")
            return _jsonrpc_error(
                request_id,
                -32010,
                "Database temporarily unavailable",
            )
        except SystemComponentNotFoundError:
            audit(
                "mcp.tool.call.error",
                tool_name=tool_name,
                arguments=arguments,
                duration_ms=(time.perf_counter() - tool_started) * 1000,
                error_code=-32004,
                error_message="System component not found",
            )
            complete("error", error_code=-32004, error_message="System component not found")
            return _jsonrpc_error(request_id, -32004, "System component not found")
        except Exception as exc:
            audit(
                "mcp.tool.call.error",
                tool_name=tool_name,
                arguments=arguments,
                duration_ms=(time.perf_counter() - tool_started) * 1000,
                error_code=-32009,
                error_message=str(exc),
            )
            complete("error", error_code=-32009, error_message="Tool execution failed")
            return _jsonrpc_error(
                request_id,
                -32009,
                "Tool execution failed",
                {"detail": str(exc)},
            )

    complete("error", error_code=-32601, error_message="Method not found")
    return _jsonrpc_error(request_id, -32601, "Method not found")
