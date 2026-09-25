"""Data model of the dependency graph: the metadata read from each block and
the core.json written by run.py.

This package is the single definition of the contract. run.py builds these
objects and serializes them with to_json(); any consumer can read a graph
back with Graph.from_json(json.load(f)). Keep the two directions in sync:
to_json() fixes the key order and decides which keys are omitted, so it is
what actually defines the file format.

One class per module:

    common.py           the closed value sets shared by the rest
    block_metadata.py   BlockMetadata — the TITLE object inside a source file
    interface.py        BlockInterface — how an FB or FC is called: parameter names per section
    node.py             Node          — one .scl/.udt file in the graph
    edge.py             Edge          — one declared dependency
    report.py           Report        — one diagnostic
    graph.py            Graph         — the root object of core.json

Two spellings of the same version coexist, on purpose:
    BlockMetadata.version   "v1.0"  — as written in the source, with the "v"
    Node.version            "1.0"   — parsed off the file name, without it
"""
from .block_metadata import BlockMetadata
from .common import CURRENT, DEPRECATED, ExternalKind, Level, ReportType, Status
from .edge import Edge
from .graph import Graph
from .interface import BlockInterface
from .node import Node
from .report import Report

__all__ = [
    "BlockInterface",
    "BlockMetadata",
    "CURRENT",
    "DEPRECATED",
    "Edge",
    "ExternalKind",
    "Graph",
    "Level",
    "Node",
    "Report",
    "ReportType",
    "Status",
]
