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

What a source says about itself has to agree, and every disagreement
is an error. The -vX.Y suffix of the file name is the reference for the
version, being what the graph resolves on: the TITLE's "version" must
be "vX.Y" and, in an .scl, the native VERSION attribute "X.Y". An .scl's
native AUTHOR and FAMILY must also equal the TITLE's "author" and
"family". A .udt is held to its name and TITLE only; a constant table,
to its name and the version in its metadata.

core.json is written whatever it found, so every finding can be read
there; the console names each error, and the script exits with 1 when
there is any.

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
from typing import Optional

import xlsx
from models import BlockInterface, BlockMetadata, Edge, ExternalKind, Graph, Node, Report

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

# An .scl's native header, between the declaration and its first VAR section:
#     AUTHOR : cyanezf
#     FAMILY : 'core/adt/queue'
#     VERSION : 3.0
HEADER_RE = re.compile(r'^\s*(?P<key>AUTHOR|FAMILY|VERSION)\s*:\s*(?P<value>.*?)\s*;?\s*$', re.IGNORECASE)
HEADER_END_RE = re.compile(r'^\s*(VAR\b|VAR_|BEGIN\b|STRUCT\b)', re.IGNORECASE)
HEADER_KEYS = ("VERSION", "AUTHOR", "FAMILY")

# The call interface: the three sections a caller fills in, and an FC's return type.
CALLABLE_RE = re.compile(r'^\s*(FUNCTION_BLOCK|FUNCTION)\s+"[^"]+"\s*(?::\s*(?P<returns>[^/]+?))?\s*(?://.*)?$',
                         re.IGNORECASE)
CALL_SECTIONS = {"VAR_INPUT": "input", "VAR_OUTPUT": "output", "VAR_IN_OUT": "inout"}
SECTION_RE = re.compile(r'^\s*(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR)\b', re.IGNORECASE)
END_VAR_RE = re.compile(r'^\s*END_VAR\b', re.IGNORECASE)
BEGIN_RE = re.compile(r'^\s*BEGIN\b', re.IGNORECASE)
# name, then optional attributes ({InstructionName := 'DTL'; ...}), then the colon.
MEMBER_RE = re.compile(r'^\s*(?P<name>"[^"]+"|[A-Za-z_]\w*)\s*(?:\{[^}]*\})?\s*:(?P<rest>.*)$')
END_STRUCT_RE = re.compile(r'^\s*END_STRUCT\b', re.IGNORECASE)


class InterfaceError(Exception):
    """A call interface that does not read the way this parser expects."""


def strip_comment(line: str) -> str:
    """Everything before a // comment. A // inside a quoted name is not a comment,
    but no name in a call interface carries one, and a string initial value would
    be on a line the parser does not need to look inside."""
    return line.split("//", 1)[0]


def parse_interface(lines: list[str]) -> Optional[BlockInterface]:
    """The call interface of an FB or FC, or None for anything else.

    Only the top level of VAR_INPUT, VAR_OUTPUT and VAR_IN_OUT is read: a
    parameter typed Struct (or Array of Struct) is one name to a caller, so its
    members are stepped over by counting Struct against END_STRUCT. Every other
    section - VAR, VAR_TEMP, VAR CONSTANT, VAR RETAIN - is walked past unread.

    Raises InterfaceError on a line it cannot place, rather than guessing: a
    parameter silently missing from the list would produce a call that looks
    right and is not.
    """
    header = next((CALLABLE_RE.match(line) for line in lines[:5] if CALLABLE_RE.match(line)), None)
    if header is None:
        return None

    interface = BlockInterface()
    if header.group(1).upper() == "FUNCTION":
        interface.returns = (header.group("returns") or "").strip() or None

    section = None      # the key in CALL_SECTIONS while inside one of the three, else "other"
    depth = 0           # Struct nesting inside the current section

    for number, raw in enumerate(lines, start=1):
        if BEGIN_RE.match(raw):
            break

        line = strip_comment(raw).strip()
        if not line or line.startswith("{"):
            continue

        if section is None:
            opened = SECTION_RE.match(line)
            if opened:
                keyword = opened.group(1).upper()
                section = CALL_SECTIONS.get(keyword, "other")
                depth = 0
            continue

        if END_VAR_RE.match(line):
            if depth != 0:
                raise InterfaceError(f"line {number}: END_VAR inside an unfinished Struct")
            section = None
            continue

        if END_STRUCT_RE.match(line):
            depth -= 1
            if depth < 0:
                raise InterfaceError(f"line {number}: END_STRUCT with no Struct open")
            continue

        member = MEMBER_RE.match(line)
        if member is None:
            if section == "other" or depth > 0:
                continue        # not read, only walked past
            raise InterfaceError(f"line {number}: not a declaration - {raw.strip()}")

        if depth == 0 and section != "other":
            getattr(interface, section).append(member.group("name").strip('"'))

        # A declaration of type Struct, or Array[..] of Struct, opens members of its own;
        # it is the only kind that ends without a semicolon.
        if member.group("rest").strip().lower().endswith("struct"):
            depth += 1

    if section is not None:
        raise InterfaceError("a VAR section is never closed")

    return interface


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


def parse_header(lines: list[str]) -> dict[str, str]:
    """An .scl's native AUTHOR, FAMILY and VERSION, keyed in upper case, with the
    single quotes TIA writes around a FAMILY taken off. Stops at the first VAR
    section, BEGIN or STRUCT, so a parameter called "version" is never read as
    the block's own. The first line of each wins."""
    header: dict[str, str] = {}
    for raw in lines:
        line = strip_comment(raw).strip()
        if HEADER_END_RE.match(line):
            break
        m = HEADER_RE.match(line)
        if m:
            header.setdefault(m.group("key").upper(), m.group("value").strip("'"))
    return header


def said(value: Optional[str]) -> str:
    return f'"{value}"' if value is not None else "nothing"


def check_source(node: Node, meta: BlockMetadata, has_title: bool,
                 header: Optional[dict[str, str]]) -> list[Report]:
    """What an .scl or .udt says about itself, held together.

    The version is written up to three times - the file name, the TITLE and an
    .scl's VERSION attribute - and the name is the reference, being what the
    graph resolves on: each of the others is compared with it rather than with
    each other, so the report names the one that is wrong. AUTHOR and FAMILY
    exist in two places only, and the TITLE is the reference. header is None
    for a .udt, whose TITLE is the only metadata it is held to.

    BlockMetadata keeps a key the TITLE does not declare as "", which is taken
    here as absent: the scan never reads an empty value.
    """
    findings: list[Report] = []
    who = f'"{node.id}"'
    version, author, family = meta.version or None, meta.author or None, meta.family or None

    if node.version is None:
        findings.append(Report.missing_version(
            f'{who}: the file name carries no -vX.Y version.', node.file))

    if not has_title:
        findings.append(Report.missing_title(
            f'{who}: there is no TITLE metadata.', node.file))
    elif version is None:
        findings.append(Report.missing_title(
            f'{who}: its TITLE declares no "version".', node.file))
    elif node.version is not None and version != f"v{node.version}":
        findings.append(Report.version_mismatch(
            f'{who}: the TITLE says version "{version}", the file name "v{node.version}".',
            node.file, version, f"v{node.version}"))

    if header is None:
        return findings

    expected = {
        "VERSION": (node.version, "the file name", node.version is not None),
        "AUTHOR": (author, "the TITLE", has_title),
        "FAMILY": (family, "the TITLE", has_title),
    }
    for key in HEADER_KEYS:
        reference, source, checkable = expected[key]
        found = header.get(key)
        if checkable and found != reference:
            findings.append(Report.header_mismatch(
                f'{who}: the header says {key} {said(found)}, {source} {said(reference)}.',
                node.file, key, found, reference))

    return findings


def check_workbook(node: Node, meta: BlockMetadata) -> list[Report]:
    """A constant table keeps the one check it always had: the version in its
    metadata against its file name, when it has both."""
    if meta.version and node.version and meta.version != f"v{node.version}":
        return [Report.version_mismatch(
            f'"{node.id}": the metadata says version "{meta.version}", the file name "v{node.version}".',
            node.file, meta.version, f"v{node.version}")]
    return []


def make_node(path: Path, name: str, meta: BlockMetadata,
              interface: Optional[BlockInterface] = None) -> Node:
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
        interface=interface,
    )


def parse_source(path: Path):
    """.scl/.udt: the symbol sits on the declaration line, the metadata on TITLE,
    an .scl's native AUTHOR, FAMILY and VERSION below it, and an FB's or FC's
    call interface in its VAR sections."""
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

    problem = None
    try:
        interface = parse_interface(lines)
    except InterfaceError as unread:
        interface, problem = None, str(unread)

    node = make_node(path, name, meta, interface)
    header = parse_header(lines) if path.suffix.lower() == ".scl" else None
    findings = check_source(node, meta, "{" in title, header)
    if problem:
        findings.append(Report.interface_unreadable(
            f'"{node.id}": its call interface could not be read - {problem}', node.file))

    return node, meta, findings


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
    node = make_node(path, name, meta)
    return node, meta, check_workbook(node, meta)


def parse_file(path: Path):
    """(Node, BlockMetadata, the file's own findings) for a file that belongs in
    the graph, else None."""
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


def build_reports(nodes: list[Node], ambiguous, unresolved, findings=()) -> list[Report]:
    """The graph's reports: each file's own findings first, ordered by file so
    that two runs over one folder write the same list, then what only the whole
    graph can say."""
    reports: list[Report] = sorted(findings, key=lambda r: r.file or "")

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
    nodes = [node for node, _, _ in parsed]
    findings = [report for _, _, found in parsed for report in found]

    by_stem, by_base = build_index(nodes)
    edges, unresolved, ambiguous = resolve(nodes, by_stem, by_base, system_names, untracked_names)
    reports = build_reports(nodes, ambiguous, unresolved, findings)

    graph = Graph(generated_at=Graph.now(), nodes=nodes, edges=edges, reports=reports)

    (core_dir / "core.json").write_text(
        json.dumps(graph.to_json(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if VIEWER_TEMPLATE.exists():
        shutil.copyfile(VIEWER_TEMPLATE, core_dir / "core.html")

    return graph


def plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def summarise(core_dir: Path, graph: Graph) -> int:
    """One line per family, then every error by name - the reports array holds the
    rest. Returns how many errors there were."""
    errors = [r for r in graph.reports if r.level == "error"]
    warnings = sum(1 for r in graph.reports if r.level == "warning")
    print(f"{core_dir.as_posix()}: {plural(len(graph.nodes), 'node')}, "
          f"{plural(len(errors), 'error')}, {plural(warnings, 'warning')}")
    for r in errors:
        print(f"  error  {r.type}  {r.message}")
    return len(errors)


def main():

    print("Run")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="plc", help="Root folder to scan for core/ folders (default: plc)")
    args = parser.parse_args()

    root = Path(args.root)
    core_dirs = find_core_dirs(root)
    if not core_dirs:
        raise SystemExit(f'No "core" folder found under {root}')

    errors = sum(summarise(core_dir, build_for_core(core_dir)) for core_dir in core_dirs)
    print("Done")
    if errors:
        raise SystemExit(1)

# To execute:
# python tools\dependency_graph_builder\run.py --root plc\s7-1x00\core

if __name__ == "__main__":
    main()
