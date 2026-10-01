"""Closed value sets shared by the rest of the model.

Status comes verbatim from a hand-written TITLE, so treat anything outside
CURRENT/DEPRECATED as unknown rather than assuming.
"""
from typing import Literal

Status = Literal["current", "deprecated"]
# What a node is, in the words the TIA Portal Add-Ins use for an object's kind:
# FUNCTION_BLOCK, FUNCTION, ORGANIZATION_BLOCK and DATA_BLOCK sources are FB, FC,
# OB and DB, a TYPE is a PlcStruct, and a constant table is a PlcTagTable.
Kind = Literal["FB", "FC", "OB", "DB", "PlcStruct", "PlcTagTable"]
Level = Literal["error", "warning", "info"]
ExternalKind = Literal["system", "untracked", "unknown"]
ReportType = Literal[
    "ambiguous-dependency",
    "broken-deprecation",
    "name-mismatch",
    "version-mismatch",
    "missing-version",
    "missing-title",
    "header-mismatch",
    "unknown-dependency",
    "system-dependency",
    "untracked-dependency",
    "interface-unreadable",
]

CURRENT: Status = "current"
DEPRECATED: Status = "deprecated"
