"""Graph — the root object of core.json."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .edge import Edge
from .node import Node
from .report import Report


@dataclass(slots=True)
class Graph:
    """Root object of core.json — one graph per PLC family."""

    generated_at: str                       # ISO-8601 with offset, second precision
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    reports: list[Report] = field(default_factory=list)

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Graph":
        return cls(
            generated_at=data["generatedAt"],
            nodes=[Node.from_json(x) for x in data["nodes"]],
            edges=[Edge.from_json(x) for x in data["edges"]],
            reports=[Report.from_json(x) for x in data["reports"]],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "generatedAt": self.generated_at,
            "nodes": [n.to_json() for n in self.nodes],
            "edges": [e.to_json() for e in self.edges],
            "reports": [r.to_json() for r in self.reports],
        }
