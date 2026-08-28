"""Edge — one declared dependency, resolved or not."""
from dataclasses import dataclass
from typing import Any, Optional

from .common import ExternalKind


@dataclass(slots=True)
class Edge:
    """One declared dependency. Use the constructors below rather than the
    fields directly: an edge only ever takes one of three shapes.

        resolved   resolved=True,  ambiguous=False
        ambiguous  resolved=False, ambiguous=True,  candidates set
        external   resolved=False, ambiguous=False, external=True, kind set

    to_json() omits the keys that do not belong to the shape at hand.
    """

    source: str                             # serialized as "from" ("from" is a keyword)
    to: str                                 # target id when resolved, else the raw name
    resolved: bool
    ambiguous: bool
    candidates: Optional[list[str]] = None  # ambiguous only
    external: Optional[bool] = None         # external only, always True when set
    kind: Optional[ExternalKind] = None     # external only

    @classmethod
    def to_node(cls, source: str, target_id: str) -> "Edge":
        return cls(source=source, to=target_id, resolved=True, ambiguous=False)

    @classmethod
    def to_ambiguous(cls, source: str, dep: str, candidates: list[str]) -> "Edge":
        return cls(source=source, to=dep, resolved=False, ambiguous=True, candidates=candidates)

    @classmethod
    def to_external(cls, source: str, dep: str, kind: ExternalKind) -> "Edge":
        return cls(source=source, to=dep, resolved=False, ambiguous=False, external=True, kind=kind)

    @property
    def is_external(self) -> bool:
        return self.external is True

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Edge":
        return cls(
            source=data["from"],
            to=data["to"],
            resolved=data["resolved"],
            ambiguous=data["ambiguous"],
            candidates=data.get("candidates"),
            external=data.get("external"),
            kind=data.get("kind"),
        )

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "from": self.source,
            "to": self.to,
            "resolved": self.resolved,
            "ambiguous": self.ambiguous,
        }
        if self.candidates is not None:
            out["candidates"] = self.candidates
        if self.external is not None:
            out["external"] = self.external
            out["kind"] = self.kind
        return out
