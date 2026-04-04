from typing import Any

from fastapi import APIRouter, Depends

from app.application import ContextService, SystemComponentNotFoundError
from app.dependencies import get_context_service

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
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if data is not None:
        payload["error"]["data"] = data
    return payload


def _read_required_component_name(arguments: dict[str, Any]) -> str:
    name = str(arguments.get("name") or "").strip()
    if not name:
        raise ValueError("argument 'name' is required")
    return name


def _tool_result(json_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "json",
                "json": json_payload,
            }
        ]
    }


@router.post("/mcp")
def handle_mcp_request(
    payload: dict[str, Any],
    context_service: ContextService = Depends(get_context_service),
):
    request_id = payload.get("id")
    if payload.get("jsonrpc") != "2.0":
        return _jsonrpc_error(request_id, -32600, "Invalid Request")

    method = payload.get("method")
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        return _jsonrpc_error(request_id, -32602, "Invalid params")

    if method == "initialize":
        protocol_version = str(params.get("protocolVersion") or "2025-03-26")
        return _jsonrpc_success(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "system-context-mcp",
                    "version": "0.1.0",
                },
            },
        )

    if method == "tools/list":
        return _jsonrpc_success(request_id, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(tool_name, str) or not tool_name.strip():
            return _jsonrpc_error(request_id, -32602, "Invalid params")
        if not isinstance(arguments, dict):
            return _jsonrpc_error(request_id, -32602, "Invalid params")

        try:
            if tool_name == "context.system.current_state":
                return _jsonrpc_success(
                    request_id,
                    _tool_result(context_service.get_system_current_state()),
                )

            if tool_name == "context.system_component.get":
                component_name = _read_required_component_name(arguments)
                environment = arguments.get("environment")
                if environment is not None:
                    environment = str(environment).strip() or None
                return _jsonrpc_success(
                    request_id,
                    _tool_result(
                        context_service.get_system_component_context(
                            component_name,
                            environment,
                        )
                    ),
                )

            if tool_name == "context.system_component.changes":
                component_name = _read_required_component_name(arguments)
                context = context_service.get_system_component_context(component_name)
                return _jsonrpc_success(
                    request_id,
                    _tool_result(
                        {
                            "system_component": context["system_component"],
                            "recent_pull_requests": context["recent_pull_requests"],
                            "recent_commits": context["recent_commits"],
                        }
                    ),
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
                return _jsonrpc_success(
                    request_id,
                    _tool_result(
                        {
                            "system_component": context["system_component"],
                            "environment": context["environment"],
                            "latest_runtime_health": context["latest_runtime_health"],
                            "latest_deployment_version": context[
                                "latest_deployment_version"
                            ],
                        }
                    ),
                )

            if tool_name == "context.system_component.dependencies":
                component_name = _read_required_component_name(arguments)
                context = context_service.get_system_component_context(component_name)
                return _jsonrpc_success(
                    request_id,
                    _tool_result(
                        {
                            "system_component": context["system_component"],
                            "dependencies": context["dependencies"],
                        }
                    ),
                )

            return _jsonrpc_error(request_id, -32601, "Method not found")
        except ValueError as exc:
            return _jsonrpc_error(request_id, -32602, "Invalid params", {"detail": str(exc)})
        except SystemComponentNotFoundError:
            return _jsonrpc_error(request_id, -32004, "System component not found")

    return _jsonrpc_error(request_id, -32601, "Method not found")
