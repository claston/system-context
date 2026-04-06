from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx


class RenderLogsConnector:
    def __init__(
        self,
        *,
        api_token: str | None = None,
        service_component_map: dict[str, str] | None = None,
        environment: str = "staging",
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
        mock_events_by_component: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.api_token = api_token.strip() if api_token else None
        self.service_component_map = {
            service_id.strip(): component_name.strip()
            for service_id, component_name in (service_component_map or {}).items()
            if service_id and service_id.strip() and component_name and component_name.strip()
        }
        self.environment = environment.strip() or "staging"
        self.mock_events_by_component = mock_events_by_component or {}
        self._client = client or httpx.Client(
            base_url="https://api.render.com/v1",
            timeout=timeout_seconds,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def _request_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._client.get(path, params=params)
        if response.status_code >= 400:
            snippet = response.text.strip().replace("\n", " ")
            if len(snippet) > 240:
                snippet = snippet[:240] + "..."
            raise RuntimeError(f"{response.status_code} for {path}: {snippet}")
        return response.json()

    def _resolve_target(self, component_name: str | None) -> tuple[str, str | None]:
        name = (component_name or "").strip()
        if name.startswith("srv-"):
            return name, None

        if name:
            for service_id, mapped_component in self.service_component_map.items():
                if mapped_component == name:
                    return service_id, mapped_component

        if len(self.service_component_map) == 1:
            service_id, mapped_component = next(iter(self.service_component_map.items()))
            return service_id, mapped_component

        raise ValueError(
            "No Render service target configured for the requested component. "
            "Provide a mapped component name or a direct srv-* service id."
        )

    def _extract_events(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            if isinstance(payload.get("logs"), list):
                return [item for item in payload.get("logs", []) if isinstance(item, dict)]
            if isinstance(payload.get("items"), list):
                return [item for item in payload.get("items", []) if isinstance(item, dict)]
            if isinstance(payload.get("events"), list):
                return [item for item in payload.get("events", []) if isinstance(item, dict)]
        return []

    def _collect_mock_events(
        self,
        *,
        component_name: str | None,
        limit: int,
    ) -> dict[str, Any] | None:
        name = (component_name or "").strip()
        if not name:
            return None
        configured = self.mock_events_by_component.get(name)
        if configured is None:
            return None
        return {
            "service_id": f"mock:{name}",
            "component_name": name,
            "environment": self.environment,
            "events": configured[: max(1, limit)],
        }
    def collect_recent_logs(
        self,
        *,
        component_name: str | None,
        start_time: datetime,
        end_time: datetime,
        limit: int,
        environment: str | None = None,
    ) -> dict[str, Any]:
        requested_environment = (environment or "").strip()
        if requested_environment and requested_environment != self.environment:
            raise ValueError(
                f"Render logs connector configured for environment '{self.environment}', "
                f"but received '{requested_environment}'."
            )

        mock_result = self._collect_mock_events(
            component_name=component_name,
            limit=limit,
        )
        if mock_result is not None:
            return {
                **mock_result,
                "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        service_id, mapped_component = self._resolve_target(component_name)
        params = {
            "resource": service_id,
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": str(max(1, limit)),
        }
        payload = self._request_json("/logs", params=params)
        events = self._extract_events(payload)
        return {
            "service_id": service_id,
            "component_name": mapped_component or component_name,
            "environment": self.environment,
            "start_time": params["startTime"],
            "end_time": params["endTime"],
            "events": events,
        }
