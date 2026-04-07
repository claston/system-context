import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("app.mcp.audit")

_SENSITIVE_KEYS = {
    "authorization",
    "x-mcp-api-key",
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
}


def _is_sensitive_key(key: str) -> bool:
    normalized_key = key.strip().lower().replace("-", "_")
    return normalized_key in _SENSITIVE_KEYS


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_as_text = str(key)
            if _is_sensitive_key(key_as_text):
                sanitized[key_as_text] = "***"
            else:
                sanitized[key_as_text] = sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_payload(item) for item in value]
    return value


def _as_preview(value: Any, max_chars: int) -> tuple[str, bool]:
    serialized = json.dumps(
        sanitize_payload(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )
    if max_chars <= 0:
        return ("...", True)
    if len(serialized) <= max_chars:
        return (serialized, False)
    return (f"{serialized[:max_chars]}...", True)


def _result_summary(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        keys = sorted([str(key) for key in result.keys()])
        return {"type": "object", "keys": keys[:20], "key_count": len(keys)}
    if isinstance(result, list):
        return {"type": "array", "item_count": len(result)}
    return {"type": type(result).__name__}


def emit_mcp_audit_event(
    event: str,
    *,
    trace_id: str,
    request_id: Any,
    method: str | None = None,
    tool_name: str | None = None,
    params: Any = None,
    arguments: Any = None,
    result: Any = None,
    outcome: str | None = None,
    error_code: int | None = None,
    error_message: str | None = None,
    duration_ms: float | None = None,
    auth: dict[str, Any] | None = None,
    max_payload_chars: int = 4000,
    include_result_body: bool = False,
) -> None:
    payload: dict[str, Any] = {
        "event": event,
        "ts": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "request_id": request_id,
    }
    if method:
        payload["method"] = method
    if tool_name:
        payload["tool_name"] = tool_name
    if params is not None:
        params_preview, params_truncated = _as_preview(params, max_payload_chars)
        payload["params_preview"] = params_preview
        payload["params_truncated"] = params_truncated
    if arguments is not None:
        arguments_preview, arguments_truncated = _as_preview(arguments, max_payload_chars)
        payload["arguments_preview"] = arguments_preview
        payload["arguments_truncated"] = arguments_truncated
    if auth is not None:
        payload["auth"] = sanitize_payload(auth)
    if result is not None:
        payload["result_summary"] = _result_summary(result)
        if include_result_body:
            result_preview, result_truncated = _as_preview(result, max_payload_chars)
            payload["result_preview"] = result_preview
            payload["result_truncated"] = result_truncated
    if duration_ms is not None:
        payload["duration_ms"] = round(duration_ms, 3)
    if outcome is not None:
        payload["outcome"] = outcome
    if error_code is not None:
        payload["error_code"] = error_code
    if error_message is not None:
        payload["error_message"] = error_message

    logger.info(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    )
