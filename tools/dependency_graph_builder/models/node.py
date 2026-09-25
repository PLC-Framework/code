"""Node — one .scl or .udt file in the graph."""
from dataclasses import dataclass
from typing import Any, Optional

from .common import DEPRECATED, Status
from .interface import BlockInterface


@dataclass(slots=True)
class Node:
    """One .scl or .udt file. Every key is always present in core.json."""

    id: str                                 # file name without extension, unique within a family
    name: str                               # TIA symbol declared on the first line
    base: str                               # id without the -vX.Y suffix; unversioned deps resolve against this
    version: Optional[str]                  # "1.0", no leading "v"; None when the name has no suffix
    status: Status                          # verbatim from TITLE, "current" when omitted
    deprecated_by: Optional[str]            # id of the replacement file
    file: str                               # forward-slash path, relative to run.py's working directory
    dependencies: list[str]                 # raw names as written in TITLE, before resolution
    interface: Optional[BlockInterface] = None  # how an FB or FC is called; None on a UDT, a table, or one that would not read

    @property
    def is_deprecated(self) -> bool:
        return self.status == DEPRECATED

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Node":
        # .get for "interface": a core.json written before the key existed
        # still reads, as a graph whose nodes say nothing about how they are called.
        interface = data.get("interface")
        return cls(
            id=data["id"],
            name=data["name"],
            base=data["base"],
            version=data["version"],
            status=data["status"],
            deprecated_by=data["deprecatedBy"],
            file=data["file"],
            dependencies=list(data["dependencies"]),
            interface=BlockInterface.from_json(interface) if interface is not None else None,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "base": self.base,
            "version": self.version,
            "status": self.status,
            "deprecatedBy": self.deprecated_by,
            "file": self.file,
            "dependencies": self.dependencies,
            "interface": self.interface.to_json() if self.interface is not None else None,
        }
