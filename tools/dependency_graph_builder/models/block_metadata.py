"""BlockMetadata — the JSON object embedded in the TITLE line of a source file."""
from dataclasses import dataclass, field
from typing import Any, Optional

from .common import CURRENT, Status


@dataclass(slots=True)
class BlockMetadata:
    """The metadata every .scl/.udt block declares on its TITLE line.

    Not part of core.json: run.py consumes only status, deprecated_by and
    dependencies from it, and derives Node.version from the file name instead.
    Built by run.py through a tolerant regex scan rather than json.loads, so a
    TITLE with a stray comma still yields the dependencies it declares.
    """

    version: str = ""                       # "v1.0" — matches the -vX.Y file suffix
    author: str = ""                        # mirrors the .scl AUTHOR attribute
    family: str = ""                        # "core/<dirs>" — mirrors the .scl FAMILY attribute
    status: Status = CURRENT
    deprecated_by: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BlockMetadata":
        return cls(
            version=data.get("version", ""),
            author=data.get("author", ""),
            family=data.get("family", ""),
            status=data.get("status", CURRENT),
            deprecated_by=data.get("deprecatedBy"),
            dependencies=list(data.get("dependencies", [])),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "author": self.author,
            "family": self.family,
            "status": self.status,
            "deprecatedBy": self.deprecated_by,
            "dependencies": self.dependencies,
        }
