#!/usr/bin/env python3
"""Build a dependency graph for PLC Framework core blocks.

Parses the TITLE metadata embedded in each .scl/.udt file under a core
folder and resolves the declared "dependencies" against the other files
in the library. Read-only: never edits any source file under --root.

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
viewer (its content is just copied from tools/deps/core.html, the
canonical source to hand-edit) that fetches ./core.json at runtime, so
it must be served over HTTP, not opened via file://.

Usage:
    python tools/dependency_graph_builder/run.py [--root plc]
"""
import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).resolve().parent
VIEWER_TEMPLATE = SCRIPT_DIR / "core.html"

NAME_RE = re.compile(
    r'^\s*(FUNCTION_BLOCK|FUNCTION|TYPE|DATA_BLOCK|ORGANIZATION_BLOCK)\s+"([^"]+)"',
    re.IGNORECASE,
)
DEP_ARRAY_RE = re.compile(r'"dependencies"\s*:\s*\[(.*?)\]', re.DOTALL)
STATUS_RE = re.compile(r'"status"\s*:\s*"([^"]+)"')
DEPRECATED_BY_RE = re.compile(r'"deprecatedBy"\s*:\s*"([^"]+)"')
QUOTED_RE = re.compile(r'"([^"]+)"')
VERSION_SUFFIX_RE = re.compile(r'^(?P<base>.+?)-v(?P<version>[0-9][\w.\-]*)$')


def parse_file(path: Path):
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

    dependencies, status, deprecated_by = [], "current", None
    for line in lines[:10]:
        if "TITLE" not in line:
            continue
        dep_match = DEP_ARRAY_RE.search(line)
        if dep_match:
            dependencies = QUOTED_RE.findall(dep_match.group(1))
        status_match = STATUS_RE.search(line)
        if status_match:
            status = status_match.group(1)
        dep_by_match = DEPRECATED_BY_RE.search(line)
        if dep_by_match:
            deprecated_by = dep_by_match.group(1)
        break

    stem = path.stem
    ver_match = VERSION_SUFFIX_RE.match(stem)
    base = ver_match.group("base") if ver_match else stem
    version = ver_match.group("version") if ver_match else None

    return {
        "id": stem,
        "name": name,
        "base": base,
        "version": version,
        "status": status,
        "deprecatedBy": deprecated_by,
        "file": path.as_posix(),
        "dependencies": dependencies,
    }


def build_index(nodes):
    by_stem = {}
    by_base = defaultdict(list)
    for n in nodes:
        by_stem[n["id"]] = n
        by_base[n["base"]].append(n)
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


def classify_external(dep: str, system_names: set, untracked_names: set) -> str:
    if dep in system_names:
        return "system"
    if dep in untracked_names:
        return "untracked"
    return "unknown"


def resolve(nodes, by_stem, by_base, system_names, untracked_names):
    edges = []
    unresolved = defaultdict(list)
    ambiguous = defaultdict(list)
    for n in nodes:
        for dep in n["dependencies"]:
            if dep in by_stem:
                edges.append({"from": n["id"], "to": dep, "resolved": True, "ambiguous": False})
                continue
            candidates = by_base.get(dep, [])
            if len(candidates) == 1:
                edges.append({"from": n["id"], "to": candidates[0]["id"], "resolved": True, "ambiguous": False})
            elif len(candidates) > 1:
                edges.append({
                    "from": n["id"], "to": dep, "resolved": False, "ambiguous": True,
                    "candidates": [c["id"] for c in candidates],
                })
                ambiguous[dep].append(n["id"])
            else:
                kind = classify_external(dep, system_names, untracked_names)
                edges.append({
                    "from": n["id"], "to": dep, "resolved": False, "ambiguous": False,
                    "external": True, "kind": kind,
                })
                unresolved[dep].append((n["id"], kind))
    return edges, unresolved, ambiguous


def build_reports(nodes, ambiguous, unresolved):
    reports = []

    for dep, users in sorted(ambiguous.items()):
        reports.append({
            "level": "error",
            "type": "ambiguous-dependency",
            "message": f'"{dep}" matches more than one file; needs a version pin.',
            "dependency": dep,
            "usedBy": users,
        })

    mismatches = [n for n in nodes if n["name"] != n["base"]]
    for n in mismatches:
        reports.append({
            "level": "warning",
            "type": "name-mismatch",
            "message": f'File name "{n["base"]}" does not match declared TIA symbol "{n["name"]}".',
            "file": n["file"],
            "base": n["base"],
            "name": n["name"],
        })

    all_ids = {x["id"] for x in nodes}
    for n in nodes:
        if n["deprecatedBy"] and n["deprecatedBy"] not in all_ids:
            reports.append({
                "level": "error",
                "type": "broken-deprecation",
                "message": f'"{n["id"]}" has deprecatedBy "{n["deprecatedBy"]}", which does not match any file.',
                "file": n["file"],
                "deprecatedBy": n["deprecatedBy"],
            })

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
            reports.append({
                "level": level,
                "type": type_,
                "message": f'"{dep}" is {note}.',
                "dependency": dep,
                "usedBy": users,
            })

    return reports


def find_core_dirs(root: Path):
    if root.name == "core" and root.is_dir():
        return [root]
    return sorted(p for p in root.rglob("core") if p.is_dir())


def build_for_core(core_dir: Path):
    files = [p for p in core_dir.rglob("*") if p.suffix.lower() in (".scl", ".udt")]
    system_names = load_name_list(core_dir, "plc-system.json")
    untracked_names = load_name_list(core_dir, "plc-untracked.json")

    nodes = [n for n in (parse_file(f) for f in files) if n]
    by_stem, by_base = build_index(nodes)
    edges, unresolved, ambiguous = resolve(nodes, by_stem, by_base, system_names, untracked_names)
    reports = build_reports(nodes, ambiguous, unresolved)

    graph = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "nodes": nodes,
        "edges": edges,
        "reports": reports,
    }

    (core_dir / "core.json").write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
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


