from datetime import datetime, timezone

from app.application.render_logs_analysis_service import RenderLogsAnalysisService


class FakeRenderLogsConnector:
    def __init__(self, events):
        self.events = events

    def collect_recent_logs(self, component_name, start_time, end_time, limit, environment=None):
        return {
            "service_id": "srv-123",
            "component_name": component_name,
            "environment": environment or "staging",
            "start_time": start_time,
            "end_time": end_time,
            "events": self.events[:limit],
        }


def test_analyze_recent_errors_groups_by_signature() -> None:
    connector = FakeRenderLogsConnector(
        [
            {
                "timestamp": "2026-04-06T12:00:00Z",
                "message": "ERROR timeout calling db request_id=abc-123",
                "source": "web",
            },
            {
                "timestamp": "2026-04-06T12:01:00Z",
                "message": "ERROR timeout calling db request_id=xyz-456",
                "source": "web",
            },
            {
                "timestamp": "2026-04-06T12:02:00Z",
                "message": "INFO request ok",
                "source": "web",
            },
        ]
    )
    service = RenderLogsAnalysisService(connector)

    result = service.analyze_recent_errors(
        component_name="micro-cardservice",
        minutes=30,
        limit=300,
        now=datetime(2026, 4, 6, 12, 5, 0, tzinfo=timezone.utc),
    )

    assert result["service_id"] == "srv-123"
    assert result["error_event_count"] == 2
    assert len(result["top_issues"]) == 1
    top_issue = result["top_issues"][0]
    assert top_issue["count"] == 2
    assert top_issue["severity"] in {"medium", "high"}
    assert "timeout" in top_issue["signature"].lower()
    assert result["likely_causes"]
    assert result["suggested_actions"]


def test_analyze_recent_errors_returns_empty_payload_without_relevant_errors() -> None:
    connector = FakeRenderLogsConnector(
        [
            {
                "timestamp": "2026-04-06T12:00:00Z",
                "message": "INFO healthy",
                "source": "worker",
            }
        ]
    )
    service = RenderLogsAnalysisService(connector)

    result = service.analyze_recent_errors(
        component_name="micro-cardservice",
        minutes=15,
        limit=100,
        now=datetime(2026, 4, 6, 12, 5, 0, tzinfo=timezone.utc),
    )

    assert result["error_event_count"] == 0
    assert result["top_issues"] == []
    assert result["likely_causes"] == []
    assert result["suggested_actions"] == []
