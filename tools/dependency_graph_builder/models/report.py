"""Report — one diagnostic about the graph."""
from dataclasses import dataclass
from typing import Any, Optional

from .common import Level, ReportType


@dataclass(slots=True)
class Report:
    """One diagnostic. level, type and message are always present; the rest
    depend on type, so use the constructors below.

        ambiguous-dependency, unknown-dependency,
        system-dependency, untracked-dependency  ->  dependency + used_by
        name-mismatch                            ->  file + base + name
        broken-deprecation                       ->  file + deprecated_by
    """

    level: Level
    type: ReportType
    message: str
    dependency: Optional[str] = None
    used_by: Optional[list[str]] = None
    file: Optional[str] = None
    base: Optional[str] = None
    name: Optional[str] = None
    deprecated_by: Optional[str] = None

    @classmethod
    def about_dependency(cls, level: Level, type_: ReportType, message: str,
                         dependency: str, used_by: list[str]) -> "Report":
        return cls(level=level, type=type_, message=message,
                   dependency=dependency, used_by=used_by)

    @classmethod
    def name_mismatch(cls, message: str, file: str, base: str, name: str) -> "Report":
        return cls(level="warning", type="name-mismatch", message=message,
                   file=file, base=base, name=name)

    @classmethod
    def broken_deprecation(cls, message: str, file: str, deprecated_by: str) -> "Report":
        return cls(level="error", type="broken-deprecation", message=message,
                   file=file, deprecated_by=deprecated_by)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Report":
        return cls(
            level=data["level"],
            type=data["type"],
            message=data["message"],
            dependency=data.get("dependency"),
            used_by=data.get("usedBy"),
            file=data.get("file"),
            base=data.get("base"),
            name=data.get("name"),
            deprecated_by=data.get("deprecatedBy"),
        )

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "level": self.level,
            "type": self.type,
            "message": self.message,
        }
        if self.dependency is not None:
            out["dependency"] = self.dependency
            out["usedBy"] = self.used_by
        if self.file is not None:
            out["file"] = self.file
        if self.base is not None:
            out["base"] = self.base
            out["name"] = self.name
        if self.deprecated_by is not None:
            out["deprecatedBy"] = self.deprecated_by
        return out
