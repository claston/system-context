from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.application.render_runtime_normalization_service import (
    RenderRuntimeNormalizationService,
    RenderRuntimeNormalizationSyncRunNotFoundError,
    UnsupportedRenderRuntimeNormalizationConnectorError,
)


class FakeRenderRuntimeRepository:
    def __init__(self) -> None:
        self.sync_runs: dict[UUID, dict] = {}
        self.raw_events_by_sync_run: dict[UUID, list[dict]] = {}
        self.system_components_by_name: dict[str, dict] = {}
        self.runtime_snapshots: dict[tuple[UUID, str, datetime], dict] = {}

    def get_sync_run_by_id(self, sync_run_id: UUID):
        return self.sync_runs.get(sync_run_id)

    def list_connector_raw_events_by_sync_run(
        self, sync_run_id: UUID, connector_name: str | None = None
    ):
        events = self.raw_events_by_sync_run.get(sync_run_id, [])
        if connector_name is None:
            return events
        return [event for event in events if event.get("connector_name") == connector_name]

    def get_system_component_by_name(self, system_component_name: str):
        return self.system_components_by_name.get(system_component_name)

    def get_runtime_snapshot_by_component_environment_and_captured_at(
        self,
        system_component_id: UUID,
        environment: str,
        captured_at: datetime,
    ):
        return self.runtime_snapshots.get((system_component_id, environment, captured_at))

    def create_runtime_snapshot(self, **kwargs):
        item = {"id": uuid4(), **kwargs}
        key = (
            kwargs["system_component_id"],
            kwargs["environment"],
            kwargs["captured_at"],
        )
        self.runtime_snapshots[key] = item
        return item

    def update_runtime_snapshot(self, runtime_snapshot_id: UUID, **kwargs):
        key = (
            kwargs["system_component_id"],
            kwargs["environment"],
            kwargs["captured_at"],
        )
        current = self.runtime_snapshots[key]
        current.update(kwargs)
        return current


def test_normalize_sync_run_creates_runtime_snapshot() -> None:
    repo = FakeRenderRuntimeRepository()
    service = RenderRuntimeNormalizationService(repo)
    sync_run_id = uuid4()
    component_id = uuid4()
    repo.sync_runs[sync_run_id] = {"id": sync_run_id, "connector_name": "render-runtime"}
    repo.system_components_by_name["micro-cardservice"] = {
        "id": component_id,
        "name": "micro-cardservice",
    }
    repo.raw_events_by_sync_run[sync_run_id] = [
        {
            "id": uuid4(),
            "connector_name": "render-runtime",
            "payload": {
                "kind": "runtime_snapshot",
                "system_component_name": "micro-cardservice",
                "environment": "staging",
                "captured_at": "2026-04-05T12:00:00Z",
                "instance_count": 2,
                "health_status": "live",
                "image_tag": "staging",
            },
        }
    ]

    summary = service.normalize_sync_run(sync_run_id)

    assert summary["raw_events_read"] == 1
    assert summary["runtime_snapshots_created"] == 1
    assert summary["runtime_snapshots_updated"] == 0
    assert summary["skipped"] == 0
    assert summary["errors"] == []


def test_normalize_sync_run_updates_existing_runtime_snapshot() -> None:
    repo = FakeRenderRuntimeRepository()
    service = RenderRuntimeNormalizationService(repo)
    sync_run_id = uuid4()
    component_id = uuid4()
    captured_at = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    repo.sync_runs[sync_run_id] = {"id": sync_run_id, "connector_name": "render-runtime"}
    repo.system_components_by_name["micro-cardservice"] = {"id": component_id}
    repo.runtime_snapshots[(component_id, "staging", captured_at)] = {
        "id": uuid4(),
        "system_component_id": component_id,
        "environment": "staging",
        "captured_at": captured_at,
        "pod_count": 1,
        "health_status": "degraded",
    }
    repo.raw_events_by_sync_run[sync_run_id] = [
        {
            "id": uuid4(),
            "connector_name": "render-runtime",
            "payload": {
                "kind": "runtime_snapshot",
                "system_component_name": "micro-cardservice",
                "environment": "staging",
                "captured_at": "2026-04-05T12:00:00Z",
                "instance_count": 3,
                "health_status": "live",
                "image_tag": "staging",
            },
        }
    ]

    summary = service.normalize_sync_run(sync_run_id)

    assert summary["runtime_snapshots_created"] == 0
    assert summary["runtime_snapshots_updated"] == 1
    updated = repo.runtime_snapshots[(component_id, "staging", captured_at)]
    assert updated["pod_count"] == 3
    assert updated["health_status"] == "live"


def test_normalize_sync_run_raises_for_missing_or_unsupported_sync_run() -> None:
    repo = FakeRenderRuntimeRepository()
    service = RenderRuntimeNormalizationService(repo)

    try:
        service.normalize_sync_run(uuid4())
    except RenderRuntimeNormalizationSyncRunNotFoundError:
        pass
    else:
        raise AssertionError("expected RenderRuntimeNormalizationSyncRunNotFoundError")

    sync_run_id = uuid4()
    repo.sync_runs[sync_run_id] = {"id": sync_run_id, "connector_name": "github"}
    try:
        service.normalize_sync_run(sync_run_id)
    except UnsupportedRenderRuntimeNormalizationConnectorError:
        pass
    else:
        raise AssertionError("expected UnsupportedRenderRuntimeNormalizationConnectorError")
