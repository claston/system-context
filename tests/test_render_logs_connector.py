from datetime import datetime, timedelta, timezone

import httpx

from app.connectors.render_logs_connector import RenderLogsConnector


def build_mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="https://api.render.com/v1", transport=transport, timeout=5.0)


def test_collect_recent_logs_uses_component_mapping() -> None:
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_params
        if request.url.path != "/v1/logs":
            return httpx.Response(404, json={"message": "not found"})
        captured_params = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "logs": [
                    {
                        "timestamp": "2026-04-06T11:00:00Z",
                        "message": "ERROR timeout while calling dependency",
                        "source": "web",
                    }
                ]
            },
        )

    connector = RenderLogsConnector(
        api_token="token",
        environment="staging",
        service_component_map={"srv-123": "micro-cardservice"},
        client=build_mock_client(handler),
    )

    end_time = datetime(2026, 4, 6, 11, 5, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(minutes=15)
    result = connector.collect_recent_logs(
        component_name="micro-cardservice",
        start_time=start_time,
        end_time=end_time,
        limit=200,
    )

    assert result["service_id"] == "srv-123"
    assert len(result["events"]) == 1
    assert captured_params["resource"] == "srv-123"
    assert captured_params["limit"] == "200"
    assert captured_params["startTime"] == "2026-04-06T10:50:00Z"
    assert captured_params["endTime"] == "2026-04-06T11:05:00Z"

def test_collect_recent_logs_accepts_direct_service_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/logs":
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"message": "not found"})

    connector = RenderLogsConnector(
        api_token="token",
        environment="staging",
        service_component_map={},
        client=build_mock_client(handler),
    )

    now = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
    result = connector.collect_recent_logs(
        component_name="srv-555",
        start_time=now - timedelta(minutes=10),
        end_time=now,
        limit=50,
    )

    assert result["service_id"] == "srv-555"
    assert result["events"] == []


def test_collect_recent_logs_uses_mock_events_when_enabled() -> None:
    connector = RenderLogsConnector(
        environment="staging",
        mock_events_by_component={
            "micro-cardservice": [
                {
                    "timestamp": "2026-04-06T11:00:00Z",
                    "message": "ERROR unhandled error traceId=abc instance=/payments/pix/charges",
                    "source": "payments",
                }
            ]
        },
    )

    end_time = datetime(2026, 4, 6, 11, 5, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(minutes=15)
    result = connector.collect_recent_logs(
        component_name="micro-cardservice",
        start_time=start_time,
        end_time=end_time,
        limit=200,
    )

    assert result["service_id"] == "mock:micro-cardservice"
    assert result["component_name"] == "micro-cardservice"
    assert result["environment"] == "staging"
    assert len(result["events"]) == 1


def test_collect_recent_logs_requires_target_service() -> None:
    connector = RenderLogsConnector(api_token="token", service_component_map={})

    now = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
    try:
        connector.collect_recent_logs(
            component_name="unknown-component",
            start_time=now - timedelta(minutes=5),
            end_time=now,
            limit=100,
        )
    except ValueError as exc:
        assert "No Render service target configured" in str(exc)
    else:
        raise AssertionError("expected ValueError")
