import logging

from app.observability import mcp_audit


def test_emit_mcp_audit_event_mirrors_to_uvicorn_error_when_no_handlers(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str]] = []
    uvicorn_logger = logging.getLogger("uvicorn.error")

    monkeypatch.setattr(mcp_audit.logger, "hasHandlers", lambda: False)
    monkeypatch.setattr(
        mcp_audit.logger,
        "info",
        lambda message: calls.append(("app.mcp.audit", message)),
    )
    monkeypatch.setattr(
        uvicorn_logger,
        "info",
        lambda message: calls.append(("uvicorn.error", message)),
    )

    mcp_audit.emit_mcp_audit_event(
        "mcp.request.received",
        trace_id="trace-1",
        request_id="req-1",
        method="tools/call",
        max_payload_chars=200,
    )

    assert any(logger_name == "app.mcp.audit" for logger_name, _ in calls)
    assert any(logger_name == "uvicorn.error" for logger_name, _ in calls)


def test_emit_mcp_audit_event_mirrors_when_handlers_are_available(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str]] = []
    uvicorn_logger = logging.getLogger("uvicorn.error")

    monkeypatch.setattr(mcp_audit.logger, "hasHandlers", lambda: True)
    monkeypatch.setattr(
        mcp_audit.logger,
        "info",
        lambda message: calls.append(("app.mcp.audit", message)),
    )
    monkeypatch.setattr(
        uvicorn_logger,
        "info",
        lambda message: calls.append(("uvicorn.error", message)),
    )

    mcp_audit.emit_mcp_audit_event(
        "mcp.request.received",
        trace_id="trace-1",
        request_id="req-1",
        method="tools/call",
        max_payload_chars=200,
    )

    assert any(logger_name == "app.mcp.audit" for logger_name, _ in calls)
    assert any(logger_name == "uvicorn.error" for logger_name, _ in calls)
