from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

import httpx

from app.connectors.base import ConnectorBatch, ConnectorRunRequest


class RenderRuntimeConnector:
    def __init__(
        self,
        *,
        api_token: str | None = None,
        service_ids: Iterable[str] | None = None,
        service_component_map: dict[str, str] | None = None,
        environment: str = "staging",
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_token = api_token.strip() if api_token else None
        self.service_ids = [item.strip() for item in (service_ids or []) if item and item.strip()]
        self.service_component_map = {
            service_id.strip(): component_name.strip()
            for service_id, component_name in (service_component_map or {}).items()
            if service_id and service_id.strip() and component_name and component_name.strip()
        }
        self.environment = environment.strip() or "staging"
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

    def _resolve_targets(self, request: ConnectorRunRequest) -> list[str]:
        component_name = (request.system_component_name or "").strip()
        if component_name:
            if component_name.startswith("srv-"):
                return [component_name]
            mapped_targets = [
                service_id
                for service_id, mapped_component in self.service_component_map.items()
                if mapped_component == component_name
            ]
            if mapped_targets:
                return mapped_targets
        configured_targets = list(self.service_ids)
        if not configured_targets:
            configured_targets = list(self.service_component_map.keys())
        return configured_targets

    def _request_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._client.get(path, params=params)
        if response.status_code >= 400:
            snippet = response.text.strip().replace("\n", " ")
            if len(snippet) > 240:
                snippet = snippet[:240] + "..."
            raise RuntimeError(f"{response.status_code} for {path}: {snippet}")
        return response.json()

    def _extract_latest_deploy(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, list):
            return payload[0] if payload else {}
        if isinstance(payload, dict):
            if isinstance(payload.get("items"), list):
                items = payload.get("items") or []
                return items[0] if items else {}
            if isinstance(payload.get("deploys"), list):
                deploys = payload.get("deploys") or []
                return deploys[0] if deploys else {}
            return payload
        return {}

    def _extract_instance_count(self, service_payload: dict[str, Any]) -> int | None:
        candidates = [
            service_payload.get("numInstances"),
            service_payload.get("num_instances"),
            (service_payload.get("service") or {}).get("numInstances"),
            (service_payload.get("service") or {}).get("num_instances"),
        ]
        for candidate in candidates:
            try:
                if candidate is None:
                    continue
                value = int(candidate)
                if value >= 0:
                    return value
            except (TypeError, ValueError):
                continue
        return None

    def _extract_image_reference(
        self, deploy_payload: dict[str, Any], service_payload: dict[str, Any]
    ) -> str | None:
        deploy_candidates = [
            deploy_payload.get("image"),
            deploy_payload.get("imageUrl"),
            deploy_payload.get("dockerImage"),
            deploy_payload.get("imageRef"),
        ]
        for candidate in deploy_candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            if isinstance(candidate, dict):
                url = str(candidate.get("url") or "").strip()
                if url:
                    return url
        service_candidates = [
            service_payload.get("image"),
            service_payload.get("imageUrl"),
            service_payload.get("dockerImage"),
            service_payload.get("imageRef"),
        ]
        for candidate in service_candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None

    def _extract_image_tag(self, image_reference: str | None) -> str | None:
        if image_reference is None:
            return None
        normalized = image_reference.strip()
        if not normalized:
            return None
        if "@" in normalized:
            return normalized.rsplit("@", 1)[1]
        tail = normalized.rsplit("/", 1)[-1]
        if ":" in tail:
            return tail.rsplit(":", 1)[1]
        return None

    def collect(self, request: ConnectorRunRequest) -> ConnectorBatch:
        targets = self._resolve_targets(request)
        if not targets:
            raise ValueError(
                "No Render service target configured. Set RENDER_SERVICE_IDS or RENDER_SERVICE_COMPONENT_MAP."
            )

        items: list[dict[str, Any]] = []
        errors: list[str] = []
        latest_cursor_by_target: dict[str, str] = {}

        for service_id in targets:
            try:
                service_payload = self._request_json(f"/services/{service_id}")
                deploys_payload = self._request_json(
                    f"/services/{service_id}/deploys",
                    {"limit": 1},
                )
                latest_deploy = self._extract_latest_deploy(deploys_payload)
                captured_at = datetime.now(timezone.utc).isoformat()
                component_name = self.service_component_map.get(service_id) or (
                    request.system_component_name or ""
                ).strip() or str(service_payload.get("name") or "").strip()
                instance_count = self._extract_instance_count(service_payload)
                health_status = str(
                    latest_deploy.get("status")
                    or service_payload.get("suspended")
                    or ""
                ).strip() or None
                image_reference = self._extract_image_reference(
                    latest_deploy,
                    service_payload,
                )
                image_tag = self._extract_image_tag(image_reference)
                deploy_id = str(latest_deploy.get("id") or "").strip()
                source_key_suffix = deploy_id or captured_at
                items.append(
                    {
                        "kind": "runtime_snapshot",
                        "service_id": service_id,
                        "system_component_name": component_name or None,
                        "environment": self.environment,
                        "captured_at": captured_at,
                        "instance_count": instance_count,
                        "health_status": health_status,
                        "image_tag": image_tag,
                        "source_key": f"runtime_snapshot:{source_key_suffix}",
                    }
                )
                latest_cursor_by_target[service_id] = captured_at
            except Exception as exc:
                errors.append(f"{service_id}: {exc}")

        return ConnectorBatch(
            connector_name="render-runtime",
            records_processed=len(items),
            items=items,
            errors=errors,
            latest_cursor_by_target=latest_cursor_by_target,
        )
