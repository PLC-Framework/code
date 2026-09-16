#!/usr/bin/env python3
"""Build a dependency graph for PLC Framework core blocks.

Parses the metadata embedded in each block under a core folder and
resolves the declared "dependencies" against the other files in the
library. Read-only: never edits any source file under --root.

Three kinds of file take part, each carrying the same metadata object:

    .scl / .udt   on the TITLE line, right below the declaration
    E*.xlsx       in the "Constants" sheet, on the row naming the table
                  (constant tables exported from TIA; workbooks whose
                  name does not start with "E" are ignored)

The version declared in that metadata is checked against the -vX.Y
suffix of the file name, which is what the graph resolves on; a
disagreement is reported as "version-mismatch" (warning).

The shape of that metadata and of the graph written out lives in
the models package — this script only fills those objects in and
serializes them.

Dependencies that don't resolve to a file are classified against two
catalogs, each a flat JSON array of names, found inside that same core
folder: plc-system.json (Siemens/TIA system blocks) and
plc-untracked.json (blocks that exist but live outside core/). Anything
matching neither is reported as "unknown-dependency" (warning).

Each PLC family has its own core/ folder (e.g. plc/s7-1x00/core/); this
script finds every folder named "core" under --root and builds an
independent graph for each one — families are never mixed together.
core.json and core.html are written straight into that core/ folder,
as committed artifacts, not build-time output. core.html is a static
viewer (its content is just copied from the core.html sitting next to
this script, the canonical source to hand-edit) that fetches
./core.json at runtime, so it must be served over HTTP, not file://.

Usage:
    python tools/dependency_graph_builder/run.py [--root plc]
"""
import argparse
import json
import re
import shutil
from pathlib import Path
from collections import defaultdict

import xlsx
from models import BlockMetadata, Edge, ExternalKind, Graph, Node, Report

SCRIPT_DIR = Path(__file__).resolve().parent
VIEWER_TEMPLATE = SCRIPT_DIR / "core.html"

SOURCE_SUFFIXES = (".scl", ".udt")
WORKBOOK_SUFFIX = ".xlsx"
WORKBOOK_PREFIX = "E"          # only the E* constant tables are part of the graph
CONSTANTS_SHEET = "Constants"
NAME_COLUMN = 1                # "Name" — holds the table symbol, e.g. "EQueueMethod"

NAME_RE = re.compile(
    r'^\s*(FUNCTION_BLOCK|FUNCTION|TYPE|DATA_BLOCK|ORGANIZATION_BLOCK)\s+"([^"]+)"',
    re.IGNORECASE,
)
DEP_ARRAY_RE = re.compile(r'"dependencies"\s*:\s*\[(.*?)\]', re.DOTALL)
VERSION_RE = re.compile(r'"version"\s*:\s*"([^"]+)"')
AUTHOR_RE = re.compile(r'"author"\s*:\s*"([^"]+)"')
FAMILY_RE = re.compile(r'"family"\s*:\s*"([^"]+)"')
STATUS_RE = re.compile(r'"status"\s*:\s*"([^"]+)"')
DEPRECATED_BY_RE = re.compile(r'"deprecatedBy"\s*:\s*"([^"]+)"')
QUOTED_RE = re.compile(r'"([^"]+)"')
VERSION_SUFFIX_RE = re.compile(r'^(?P<base>.+?)-v(?P<version>[0-9][\w.\-]*)$')


def parse_metadata(text: str) -> BlockMetadata:
    """Read the metadata object field by field instead of with json.loads, so
    a hand-edited one — a stray comma, a Windows path left unescaped — still
    yields everything it declares."""
    meta = BlockMetadata()
    dep_match = DEP_ARRAY_RE.search(text)
    if dep_match:
        meta.dependencies = QUOTED_RE.findall(dep_match.group(1))
    for rx, attr in ((VERSION_RE, "version"), (AUTHOR_RE, "author"),
                     (FAMILY_RE, "family"), (STATUS_RE, "status"),
                     (DEPRECATED_BY_RE, "deprecated_by")):
        m = rx.search(text)
        if m:
            setattr(meta, attr, m.group(1))
    return meta


def make_node(path: Path, name: str, meta: BlockMetadata) -> Node:
    """Assemble a node: the id and version come from the file name, the rest
    from the metadata the file declares."""
    stem = path.stem
    ver_match = VERSION_SUFFIX_RE.match(stem)
    return Node(
        id=stem,
        name=name,
        base=ver_match.group("base") if ver_match else stem,
        version=ver_match.group("version") if ver_match else None,
        status=meta.status,
        deprecated_by=meta.deprecated_by,
        file=path.as_posix(),
        dependencies=meta.dependencies,
    )


def parse_source(path: Path):
    """.scl/.udt: the symbol sits on the declaration line, the metadata on TITLE."""
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return None

    name = None
    for line in lines[:5]:
        m = NAME_RE.match(line)
        if m:
            name = m.group(2)
            break
    if name is None:
        return None

    title = next((line for line in lines[:10] if "TITLE" in line), "")
    meta = parse_metadata(title)
    return make_node(path, name, meta), meta


def parse_workbook(path: Path):
    """E*.xlsx: in the Constants sheet, the row that names the table also
    carries the metadata in its Comment cell — usually row 2, right under
    the header. Look it up by content rather than by a fixed column, so a
    table with an extra column still works."""
    try:
        rows = xlsx.sheet_rows(path, CONSTANTS_SHEET)
    except xlsx.XlsxError:
        return None

    meta_row, meta_text = None, ""
    for row_number in sorted(rows):
        for _, value in sorted(rows[row_number].items()):
            candidate = value.strip()
            if candidate.startswith("{") and '"dependencies"' in candidate:
                meta_row, meta_text = row_number, candidate
                break
        if meta_text:
            break

    row = rows.get(meta_row) if meta_row else rows.get(2)
    name = (row or {}).get(NAME_COLUMN, "").strip()
    if not name:
        return None

    meta = parse_metadata(meta_text)
    return make_node(path, name, meta), meta


def parse_file(path: Path):
    """(Node, BlockMetadata) for a file that belongs in the graph, else None."""
    suffix = path.suffix.lower()
    if suffix in SOURCE_SUFFIXES:
        return parse_source(path)
    if suffix == WORKBOOK_SUFFIX and path.name.startswith(WORKBOOK_PREFIX):
        return parse_workbook(path)
    return None


def build_index(nodes: list[Node]):
    by_stem = {}
    by_base = defaultdict(list)
    for n in nodes:
        by_stem[n.id] = n
        by_base[n.base].append(n)
    return by_stem, by_base


def load_name_list(root: Path, filename: str) -> set:
    names = set()
    for path in root.rglob(filename):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, list):
            names.update(str(x) for x in data)
    return names


def classify_external(dep: str, system_names: set, untracked_names: set) -> ExternalKind:
    if dep in system_names:
        return "system"
    if dep in untracked_names:
        return "untracked"
    return "unknown"


def resolve(nodes: list[Node], by_stem, by_base, system_names, untracked_names):
    edges: list[Edge] = []
    unresolved = defaultdict(list)
    ambiguous = defaultdict(list)
    for n in nodes:
        for dep in n.dependencies:
            if dep in by_stem:
                edges.append(Edge.to_node(n.id, dep))
                continue
            candidates = by_base.get(dep, [])
            if len(candidates) == 1:
                edges.append(Edge.to_node(n.id, candidates[0].id))
            elif len(candidates) > 1:
                edges.append(Edge.to_ambiguous(n.id, dep, [c.id for c in candidates]))
                ambiguous[dep].append(n.id)
            else:
                kind = classify_external(dep, system_names, untracked_names)
                edges.append(Edge.to_external(n.id, dep, kind))
                unresolved[dep].append((n.id, kind))
    return edges, unresolved, ambiguous


def build_reports(nodes: list[Node], ambiguous, unresolved, declared_versions) -> list[Report]:
    reports: list[Report] = []

    for dep, users in sorted(ambiguous.items()):
        reports.append(Report.about_dependency(
            "error", "ambiguous-dependency",
            f'"{dep}" matches more than one file; needs a version pin.',
            dep, users,
        ))

    mismatches = [n for n in nodes if n.name != n.base]
    for n in mismatches:
        reports.append(Report.name_mismatch(
            f'File name "{n.base}" does not match declared TIA symbol "{n.name}".',
            n.file, n.base, n.name,
        ))

    for n in nodes:
        declared = declared_versions.get(n.id)
        if declared and n.version and declared != f"v{n.version}":
            reports.append(Report.version_mismatch(
                f'"{n.id}" declares version "{declared}" in its metadata, '
                f'but the file name says "v{n.version}".',
                n.file, declared, f"v{n.version}",
            ))

    all_ids = {x.id for x in nodes}
    for n in nodes:
        if n.deprecated_by and n.deprecated_by not in all_ids:
            reports.append(Report.broken_deprecation(
                f'"{n.id}" has deprecatedBy "{n.deprecated_by}", which does not match any file.',
                n.file, n.deprecated_by,
            ))

    for dep in sorted(unresolved):
        users_by_kind = defaultdict(list)
        for node_id, kind in unresolved[dep]:
            users_by_kind[kind].append(node_id)
        for kind, users in users_by_kind.items():
            if kind == "system":
                level, type_, note = "info", "system-dependency", "a Siemens/TIA system block (listed in plc-system.json)"
            elif kind == "untracked":
                level, type_, note = "info", "untracked-dependency", "a block outside core/ (listed in plc-untracked.json)"
            else:
                level, type_, note = "warning", "unknown-dependency", "not defined in the repo and not listed in plc-system.json or plc-untracked.json"
            reports.append(Report.about_dependency(
                level, type_, f'"{dep}" is {note}.', dep, users,
            ))

    return reports


def find_core_dirs(root: Path):
    if root.name == "core" and root.is_dir():
        return [root]
    return sorted(p for p in root.rglob("core") if p.is_dir())


def build_for_core(core_dir: Path) -> Graph:
    files = core_dir.rglob("*")          # parse_file skips whatever is not a block
    system_names = load_name_list(core_dir, "plc-system.json")
    untracked_names = load_name_list(core_dir, "plc-untracked.json")

    parsed = [p for p in (parse_file(f) for f in files) if p]
    nodes = [node for node, _ in parsed]
    declared_versions = {node.id: meta.version for node, meta in parsed if meta.version}

    by_stem, by_base = build_index(nodes)
    edges, unresolved, ambiguous = resolve(nodes, by_stem, by_base, system_names, untracked_names)
    reports = build_reports(nodes, ambiguous, unresolved, declared_versions)

    graph = Graph(generated_at=Graph.now(), nodes=nodes, edges=edges, reports=reports)

    (core_dir / "core.json").write_text(
        json.dumps(graph.to_json(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if VIEWER_TEMPLATE.exists():
        shutil.copyfile(VIEWER_TEMPLATE, core_dir / "core.html")

    return graph


def main():

    print("Run")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="plc", help="Root folder to scan for core/ folders (default: plc)")
    args = parser.parse_args()

    root = Path(args.root)
    core_dirs = find_core_dirs(root)
    if not core_dirs:
        raise SystemExit(f'No "core" folder found under {root}')

    for core_dir in core_dirs:
        build_for_core(core_dir)
    print("Done")

# To execute:
# python tools\dependency_graph_builder\run.py --root plc\s7-1x00\core

if __name__ == "__main__":
    main()
