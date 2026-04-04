from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ConnectorRunRequest:
    system_component_name: str | None = None
    cursor_by_target: dict[str, str] = field(default_factory=dict)


@dataclass
class ConnectorBatch:
    connector_name: str
    records_processed: int
    items: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    latest_cursor_by_target: dict[str, str] = field(default_factory=dict)


class Connector(Protocol):
    def collect(self, request: ConnectorRunRequest) -> ConnectorBatch: ...
