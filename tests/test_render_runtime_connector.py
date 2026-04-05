import json

import httpx

from app.connectors.base import ConnectorRunRequest
from app.connectors.render_runtime_connector import RenderRuntimeConnector


def build_mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="https://api.render.com/v1", transport=transport, timeout=5.0)


def test_collect_reads_runtime_snapshot_for_service() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/services/srv-123":
            return httpx.Response(
                200,
                json={
                    "id": "srv-123",
                    "name": "micro-cardservice",
                    "numInstances": 2,
                },
            )
        if request.url.path == "/v1/services/srv-123/deploys":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "dep-1",
                        "status": "live",
                        "image": {"url": "ghcr.io/claston/system-context:staging"},
                    }
                ],
            )
        return httpx.Response(404, json={"message": "not found"})

    connector = RenderRuntimeConnector(
        api_token="token",
        environment="staging",
        service_ids=["srv-123"],
        service_component_map={"srv-123": "micro-cardservice"},
        client=build_mock_client(handler),
    )

    batch = connector.collect(
        ConnectorRunRequest(system_component_name="micro-cardservice")
    )

    assert batch.connector_name == "render-runtime"
    assert batch.records_processed == 1
    assert batch.errors == []
    payload = batch.items[0]
    assert payload["kind"] == "runtime_snapshot"
    assert payload["service_id"] == "srv-123"
    assert payload["system_component_name"] == "micro-cardservice"
    assert payload["instance_count"] == 2
    assert payload["health_status"] == "live"
    assert payload["image_tag"] == "staging"
    assert payload["source_key"] == "runtime_snapshot:dep-1"


def test_collect_reports_errors_and_continues_other_services() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/v1/services/srv-broken/"):
            return httpx.Response(500, text=json.dumps({"message": "boom"}))
        if request.url.path == "/v1/services/srv-ok":
            return httpx.Response(200, json={"id": "srv-ok", "name": "ok", "numInstances": 1})
        if request.url.path == "/v1/services/srv-ok/deploys":
            return httpx.Response(200, json=[{"id": "dep-ok", "status": "live"}])
        return httpx.Response(404, json={"message": "not found"})

    connector = RenderRuntimeConnector(
        api_token="token",
        environment="staging",
        service_ids=["srv-broken", "srv-ok"],
        client=build_mock_client(handler),
    )

    batch = connector.collect(ConnectorRunRequest())

    assert batch.records_processed == 1
    assert len(batch.items) == 1
    assert len(batch.errors) == 1
    assert "srv-broken" in batch.errors[0]


def test_collect_requires_configured_target_service() -> None:
    connector = RenderRuntimeConnector(api_token="token", service_ids=[])

    try:
        connector.collect(ConnectorRunRequest())
    except ValueError as exc:
        assert "No Render service target configured" in str(exc)
    else:
        raise AssertionError("expected ValueError")
