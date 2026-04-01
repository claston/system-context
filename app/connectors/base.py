from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ConnectorRunRequest:
    system_component_name: str | None = None


@dataclass
class ConnectorBatch:
    connector_name: str
    records_processed: int
    items: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Connector(Protocol):
    def collect(self, request: ConnectorRunRequest) -> ConnectorBatch: ...
