from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.connectors.render_logs_connector import RenderLogsConnector

ERROR_PATTERN = re.compile(
    r"(error|exception|traceback|fatal|timeout|panic|failed|failure|5\d{2})",
    re.IGNORECASE,
)


class RenderLogsAnalysisService:
    def __init__(self, connector: RenderLogsConnector) -> None:
        self.connector = connector

    def _validate_window(self, minutes: int, limit: int) -> None:
        if minutes < 1 or minutes > 180:
            raise ValueError("argument 'minutes' must be between 1 and 180")
        if limit < 1 or limit > 1000:
            raise ValueError("argument 'limit' must be between 1 and 1000")

    def _extract_message(self, event: dict[str, Any]) -> str:
        for key in ("message", "text", "line", "log", "msg"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _extract_source(self, event: dict[str, Any]) -> str:
        for key in ("source", "stream", "service", "container"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "unknown"

    def _event_matches_error(self, event: dict[str, Any], message: str) -> bool:
        if ERROR_PATTERN.search(message):
            return True
        status_code = event.get("status_code") or event.get("statusCode")
        try:
            return int(status_code) >= 500
        except (TypeError, ValueError):
            return False

    def _normalize_signature(self, message: str) -> str:
        normalized = message.lower()
        normalized = re.sub(r"\b(request_?id|trace_?id|correlation_?id)=[^\s]+\b", r"\1=<id>", normalized)
        normalized = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27}\b", "<id>", normalized)
        normalized = re.sub(r"\b[a-z0-9]+-[a-z0-9-]{4,}\b", "<id>", normalized)
        normalized = re.sub(r"\b[0-9a-f]{7,40}\b", "<hash>", normalized)
        normalized = re.sub(r"\b\d+\b", "<n>", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if len(normalized) > 200:
            normalized = normalized[:200].rstrip()
        return normalized or "unknown error signature"

    def _classify_severity(self, signature: str, count: int) -> str:
        if any(token in signature for token in ("fatal", "panic", "traceback", "exception")):
            return "high"
        if "5" in signature and "5<n><n>" in signature:
            return "high"
        if count >= 5:
            return "high"
        return "medium"

    def _classify_cause_and_action(self, signature: str) -> tuple[str, str]:
        mapping = [
            (
                re.compile(r"(timeout|timed out)", re.IGNORECASE),
                "Dependency timeout",
                "Check dependency latency and timeout/retry settings.",
            ),
            (
                re.compile(r"(unauthorized|forbidden|token|jwt|auth)", re.IGNORECASE),
                "Authentication or authorization issue",
                "Validate credentials, token expiration and permission scope.",
            ),
            (
                re.compile(r"(connection refused|econnrefused|dns|name resolution)", re.IGNORECASE),
                "Dependency connectivity issue",
                "Verify endpoint host, DNS resolution and dependency health.",
            ),
            (
                re.compile(r"(rate limit|too many requests|429)", re.IGNORECASE),
                "Rate limit reached",
                "Add backoff and reduce burst traffic for the affected operation.",
            ),
            (
                re.compile(r"(out of memory|oom|killed)", re.IGNORECASE),
                "Memory pressure",
                "Review memory usage and adjust instance size or workload profile.",
            ),
        ]
        for pattern, cause, action in mapping:
            if pattern.search(signature):
                return cause, action
        return (
            "Unhandled runtime failure",
            "Inspect sample logs and stack trace to identify the failing code path.",
        )

    def analyze_recent_errors(
        self,
        component_name: str,
        *,
        minutes: int = 30,
        limit: int = 300,
        environment: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self._validate_window(minutes, limit)
        if now is None:
            now = datetime.now(timezone.utc)
        start_time = now - timedelta(minutes=minutes)
        result = self.connector.collect_recent_logs(
            component_name=component_name,
            start_time=start_time,
            end_time=now,
            limit=limit,
            environment=environment,
        )
        events = result.get("events", [])

        grouped: dict[str, dict[str, Any]] = {}
        sample_lines: list[str] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            message = self._extract_message(event)
            if not message or not self._event_matches_error(event, message):
                continue
            signature = self._normalize_signature(message)
            source = self._extract_source(event)
            bucket = grouped.setdefault(
                signature,
                {
                    "signature": signature,
                    "count": 0,
                    "sample_message": message,
                    "affected_sources": set(),
                },
            )
            bucket["count"] += 1
            bucket["affected_sources"].add(source)
            if len(sample_lines) < 8:
                sample_lines.append(message)

        top_issues: list[dict[str, Any]] = []
        likely_causes: list[str] = []
        suggested_actions: list[str] = []
        for signature, bucket in sorted(
            grouped.items(),
            key=lambda item: item[1]["count"],
            reverse=True,
        )[:10]:
            severity = self._classify_severity(signature, bucket["count"])
            cause, action = self._classify_cause_and_action(signature)
            top_issues.append(
                {
                    "signature": signature,
                    "count": bucket["count"],
                    "severity": severity,
                    "sample_message": bucket["sample_message"],
                    "affected_sources": sorted(bucket["affected_sources"]),
                    "novelty": "unknown",
                }
            )
            if cause not in likely_causes:
                likely_causes.append(cause)
            if action not in suggested_actions:
                suggested_actions.append(action)

        return {
            "system_component": component_name,
            "service_id": result.get("service_id"),
            "environment": result.get("environment"),
            "window": {
                "minutes": minutes,
                "start_time": result.get("start_time"),
                "end_time": result.get("end_time"),
            },
            "error_event_count": sum(item["count"] for item in top_issues),
            "top_issues": top_issues,
            "likely_causes": likely_causes,
            "suggested_actions": suggested_actions,
            "sample_log_lines": sample_lines[:5],
        }
