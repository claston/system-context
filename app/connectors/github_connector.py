from app.connectors.base import ConnectorBatch, ConnectorRunRequest


class GithubConnector:
    def collect(self, request: ConnectorRunRequest) -> ConnectorBatch:
        component = request.system_component_name or "all-components"
        items = [
            {"kind": "pull_request", "component": component, "id": "pr-1"},
            {"kind": "commit", "component": component, "id": "commit-1"},
        ]
        return ConnectorBatch(
            connector_name="github",
            records_processed=len(items),
            items=items,
        )
