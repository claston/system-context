from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.repositories import RenderRuntimeNormalizationRepository


class RenderRuntimeNormalizationSyncRunNotFoundError(Exception):
    pass


class UnsupportedRenderRuntimeNormalizationConnectorError(Exception):
    pass


class RenderRuntimeNormalizationService:
    _DEPLOY_RESTART_GRACE_WINDOW = timedelta(minutes=10)

    def __init__(
        self, normalization_repository: RenderRuntimeNormalizationRepository
    ) -> None:
        self.normalization_repository = normalization_repository

    def normalize_sync_run(self, sync_run_id: UUID) -> dict[str, Any]:
        sync_run = self.normalization_repository.get_sync_run_by_id(sync_run_id)
        if sync_run is None:
            raise RenderRuntimeNormalizationSyncRunNotFoundError(
                f"sync run not found: {sync_run_id}"
            )

        connector_name = self._get_value(sync_run, "connector_name")
        if connector_name != "render-runtime":
            raise UnsupportedRenderRuntimeNormalizationConnectorError(
                "unsupported connector for render runtime normalization: "
                f"{connector_name}"
            )

        raw_events = self.normalization_repository.list_connector_raw_events_by_sync_run(
            sync_run_id=sync_run_id,
            connector_name="render-runtime",
        )
        summary = {
            "sync_run_id": sync_run_id,
            "connector_name": "render-runtime",
            "raw_events_read": len(raw_events),
            "runtime_snapshots_created": 0,
            "runtime_snapshots_updated": 0,
            "operational_issues_opened": 0,
            "operational_issues_updated": 0,
            "operational_issues_skipped_deploy_related": 0,
            "skipped": 0,
            "errors": [],
        }

        for raw_event in raw_events:
            payload = self._get_value(raw_event, "payload")
            if not isinstance(payload, dict):
                summary["skipped"] += 1
                summary["errors"].append(
                    f"raw event {self._get_value(raw_event, 'id')} has invalid payload"
                )
                continue
            kind = str(payload.get("kind") or "").strip()
            if kind != "runtime_snapshot":
                summary["skipped"] += 1
                continue

            component_name = str(payload.get("system_component_name") or "").strip()
            if not component_name:
                summary["skipped"] += 1
                summary["errors"].append(
                    f"missing system_component_name for raw event {self._get_value(raw_event, 'id')}"
                )
                continue
            system_component = self.normalization_repository.get_system_component_by_name(
                component_name
            )
            if system_component is None:
                summary["skipped"] += 1
                summary["errors"].append(
                    f"system component not found: {component_name}"
                )
                continue

            environment = (
                str(payload.get("environment") or "").strip() or "staging"
            )
            captured_at = self._parse_iso_datetime(payload.get("captured_at"))
            if captured_at is None:
                captured_at = datetime.now(timezone.utc)
            pod_count = self._parse_non_negative_int(payload.get("instance_count"))
            health_status = self._optional_string(payload.get("health_status"))
            image_tag = self._optional_string(payload.get("image_tag"))
            data = {
                "system_component_id": self._get_value(system_component, "id"),
                "environment": environment,
                "captured_at": captured_at,
                "pod_count": pod_count,
                "restart_count": None,
                "health_status": health_status,
                "image_tag": image_tag,
            }
            existing_snapshot = self.normalization_repository.get_runtime_snapshot_by_component_environment_and_captured_at(
                data["system_component_id"],
                environment,
                captured_at,
            )
            if existing_snapshot is None:
                self.normalization_repository.create_runtime_snapshot(**data)
                summary["runtime_snapshots_created"] += 1
            else:
                runtime_snapshot_id = self._get_value(existing_snapshot, "id")
                self.normalization_repository.update_runtime_snapshot(
                    runtime_snapshot_id,
                    **data,
                )
                summary["runtime_snapshots_updated"] += 1

            issue_action = self._upsert_unexpected_restart_issue(
                system_component_id=data["system_component_id"],
                environment=environment,
                payload=payload,
            )
            if issue_action == "opened":
                summary["operational_issues_opened"] += 1
            elif issue_action == "updated":
                summary["operational_issues_updated"] += 1
            elif issue_action == "deploy_related":
                summary["operational_issues_skipped_deploy_related"] += 1

        return summary

    def _upsert_unexpected_restart_issue(
        self,
        *,
        system_component_id: UUID,
        environment: str,
        payload: dict[str, Any],
    ) -> str | None:
        last_deploy_at = self._parse_iso_datetime(payload.get("last_deploy_at"))
        restart_candidate = self._select_unexpected_restart_candidate(
            payload.get("restart_candidates"),
            last_deploy_at=last_deploy_at,
        )
        if restart_candidate is None:
            if self._has_deploy_related_restart_candidate(
                payload.get("restart_candidates"),
                last_deploy_at=last_deploy_at,
            ):
                return "deploy_related"
            return None

        occurred_at = restart_candidate["occurred_at"]
        existing = self.normalization_repository.get_open_operational_issue(
            system_component_id=system_component_id,
            environment=environment,
            issue_type="unexpected_restart",
        )
        evidence_source = restart_candidate["source"]
        evidence_payload = {
            "event_type": restart_candidate["event_type"],
            "occurred_at": occurred_at.isoformat(),
        }
        confidence = self._resolve_confidence(evidence_source)
        if existing is None:
            self.normalization_repository.create_operational_issue(
                system_component_id=system_component_id,
                environment=environment,
                issue_type="unexpected_restart",
                status="open",
                first_seen_at=occurred_at,
                last_seen_at=occurred_at,
                evidence_source=evidence_source,
                evidence_payload=evidence_payload,
                confidence=confidence,
            )
            return "opened"

        existing_last_seen = self._parse_iso_datetime(self._get_value(existing, "last_seen_at"))
        if existing_last_seen is not None and existing_last_seen >= occurred_at:
            return None
        self.normalization_repository.update_operational_issue(
            self._get_value(existing, "id"),
            last_seen_at=occurred_at,
            evidence_source=evidence_source,
            evidence_payload=evidence_payload,
            confidence=confidence,
        )
        return "updated"

    def _resolve_confidence(self, source: str) -> str:
        normalized = source.strip().lower()
        if normalized == "events":
            return "high"
        if normalized == "instances":
            return "medium"
        return "low"

    def _has_deploy_related_restart_candidate(
        self, candidates: Any, *, last_deploy_at: datetime | None
    ) -> bool:
        parsed_candidates = self._parse_restart_candidates(candidates)
        return any(
            self._is_deploy_related_restart(item["occurred_at"], last_deploy_at)
            for item in parsed_candidates
        )

    def _select_unexpected_restart_candidate(
        self,
        candidates: Any,
        *,
        last_deploy_at: datetime | None,
    ) -> dict[str, Any] | None:
        parsed_candidates = self._parse_restart_candidates(candidates)
        for candidate in parsed_candidates:
            if self._is_deploy_related_restart(
                candidate["occurred_at"],
                last_deploy_at,
            ):
                continue
            return candidate
        return None

    def _is_deploy_related_restart(
        self, restart_at: datetime, deploy_at: datetime | None
    ) -> bool:
        if deploy_at is None:
            return False
        window_end = deploy_at + self._DEPLOY_RESTART_GRACE_WINDOW
        return deploy_at <= restart_at <= window_end

    def _parse_restart_candidates(self, candidates: Any) -> list[dict[str, Any]]:
        if not isinstance(candidates, list):
            return []
        parsed: list[dict[str, Any]] = []
        for raw_item in candidates:
            if not isinstance(raw_item, dict):
                continue
            occurred_at = self._parse_iso_datetime(raw_item.get("occurred_at"))
            if occurred_at is None:
                continue
            parsed.append(
                {
                    "occurred_at": occurred_at,
                    "source": str(raw_item.get("source") or "unknown").strip()
                    or "unknown",
                    "event_type": str(raw_item.get("event_type") or "unknown").strip()
                    or "unknown",
                }
            )
        parsed.sort(key=lambda item: item["occurred_at"], reverse=True)
        return parsed

    def _parse_iso_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        normalized = str(value).strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _parse_non_negative_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        if parsed < 0:
            return None
        return parsed

    def _optional_string(self, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    def _get_value(self, item: Any, field: str) -> Any:
        if isinstance(item, dict):
            return item.get(field)
        return getattr(item, field, None)
