# Dependency graph

`run.py` builds a dependency graph between `core/` blocks (`.scl`/`.udt`), reading the JSON embedded in each file's `TITLE` line. It only reads under `--root` (`plc/` by default) — it never modifies source files.

Each PLC family has its own `core/` folder (e.g. `plc/s7-1x00/core/`). The script finds every folder named `core` under `--root` and builds an **independent graph per family** — blocks from different families are never mixed together. For each `core/` folder found, it writes `core.json` and `core.html` **directly inside that folder**.

`core.json` is a **committed artifact**, not build output: only the repo maintainer runs this script (whenever a `core/` folder changes) and commits the regenerated files.

`core.html` is a **static viewer**. Its canonical, hand-maintained source is `tools/dependency_graph_builder/core.html` — edit it there if the visualization needs changes; the script copies it byte-for-byte into every `core/` folder it processes, so all families share the exact same viewer. It loads its sibling `core.json` at runtime via `fetch("./core.json")`, so it must be served over HTTP (GitHub Pages, `python -m http.server`, any static host). Opening it directly with a double-click (`file://`) will fail — Chrome/Edge block local `fetch()` under that protocol; the page shows an explanatory error in that case instead of a blank screen.

## Usage

```shell
python tools/dependency_graph_builder/run.py [--root plc]
```

- `--root` — root folder to search for `core/` folders (defaults to `plc`). If `--root` itself is named `core`, it is treated as the single family to build.

Example (defaults, run from the repo root after touching any `core/` folder):

```shell
python tools/dependency_graph_builder/run.py
```

To preview a family's `core.html` locally:

```shell
python -m http.server 8000 --directory plc/s7-1x00/core
```

then open `http://localhost:8000/core.html`.

## Metadata expected in each file

```shell
FUNCTION "_priorityQueue" : Int
TITLE = {"version":"v1.0","author":"cyanezf","family":"core/adt/priority-queue","status":"current","deprecatedBy":null,"dependencies":["priorityQueueInstanceAttributes-v1.0","MOVE_BLK_VARIANT"]}
```

Every `.scl` and `.udt` under `core/` carries the same six keys, in that order:

| Key            | Description                                                                                                                                                     |
| :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `version`      | Version **with** the leading `v` (`"v1.0"`), matching the `-vX.Y` suffix of the file name and, in `.scl`, the native `VERSION :` attribute.                     |
| `author`       | Author of the block, mirroring the `.scl` `AUTHOR :` attribute.                                                                                                 |
| `family`       | Folder path of the block as `core/<dirs>`, mirroring the `.scl` `FAMILY :` attribute.                                                                           |
| `status`       | `"current"` (default when omitted) or `"deprecated"`.                                                                                                           |
| `deprecatedBy` | `id` of the file that replaces this one when `status` is `"deprecated"`, else `null`. Must match another file's `id` exactly, or it becomes a `broken-deprecation` report. |
| `dependencies` | Names of other blocks/UDTs it depends on. May include a version (`"_foo-v1.0"`) when several versions of the same block coexist, or just the plain name when only one exists. |

All six are read into a `BlockMetadata` (see [`models/`](models/)), but only `status`, `deprecatedBy` and `dependencies` reach `core.json`: `version`, `author` and `family` stay in the sources, and the node's `version` is derived from the file name instead.

## Catalogs: `plc-system.json` / `plc-untracked.json`

Each `core/` folder may contain two flat JSON arrays of names, used to classify dependencies that don't resolve to any file in that family:

- **`plc-system.json`** — Siemens/TIA system blocks (`TON_TIME`, `MC_MOVEABSOLUTE`, `TCON`, ...).
- **`plc-untracked.json`** — blocks that genuinely exist but live outside `core/` (e.g. device-specific UDTs maintained elsewhere).

A dependency matching neither is reported as `unknown-dependency` — either add it to the right catalog or treat it as a real problem (typo, missing block).

## Output

The console only gets the `Run` / `Done` progress markers — all diagnostics live in the `reports` array of `core.json` instead.

### `core.json`

```json
{
  "generatedAt": "2026-07-12T12:54:20+00:00",
  "nodes": [ ... ],
  "edges": [ ... ],
  "reports": [ ... ]
}
```

### Node fields

| Field          | Description                                                                         |
| :------------- | :------------------------------------------------------------------------------------ |
| `id`           | File name without extension (e.g. `_priorityQueue-v1.0`).                             |
| `name`         | TIA symbol declared on the first line (`FUNCTION "_priorityQueue"` → `_priorityQueue`). |
| `base`         | `id` with the `-vX.Y` suffix stripped. Used to resolve unversioned dependency references. |
| `version`      | Version extracted from the file name, **without** the leading `v` (`"1.0"`), or `null` if it has no `-vX.Y` suffix. |
| `status`       | `"current"` or `"deprecated"`, from `TITLE` (defaults to `"current"`).                |
| `deprecatedBy` | `id` of the file that replaces this one, or `null`.                                   |
| `file`         | Relative path to the file.                                                            |
| `dependencies` | Raw dependency list as it appears in `TITLE`.                                         |

### Edge fields

| Field        | Description                                                                                          |
| :----------- | :------------------------------------------------------------------------------------------------------|
| `from`       | `id` of the node declaring the dependency.                                                            |
| `to`         | `id` of the resolved node, or the raw name if it could not be resolved.                               |
| `resolved`   | `true` if a matching file was found.                                                                  |
| `ambiguous`  | `true` if the unversioned name matches more than one file — needs a version pin.                      |
| `candidates` | Only present when `ambiguous`: list of candidate `id`s.                                               |
| `external`   | Only present when unresolved: `true` if it matches no file in the family (system/untracked/unknown).  |
| `kind`       | Only present when `external`: `"system"`, `"untracked"`, or `"unknown"` (see catalogs above).         |

### Report fields

| Field          | Description                                                                                          |
| :------------- | :-------------------------------------------------------------------------------------------------------|
| `level`        | `"error"`, `"warning"`, or `"info"`.                                                                     |
| `type`         | See report types below.                                                                                  |
| `message`      | Human-readable description of the finding.                                                               |
| `dependency`   | The dependency name involved (`*-dependency` reports only).                                              |
| `usedBy`       | `id`s of the nodes that declare this dependency (`*-dependency` reports only).                            |
| `file`         | The file involved (`name-mismatch` / `broken-deprecation` reports only).                                  |
| `base`, `name` | The two mismatched names (`name-mismatch` reports only).                                                  |
| `deprecatedBy` | The dangling value (`broken-deprecation` reports only).                                                   |

Report types:

1. **`ambiguous-dependency`** (`error`) — an unversioned name matches more than one file; needs a version pin.
2. **`broken-deprecation`** (`error`) — a file's `deprecatedBy` doesn't match any file's `id` (typo, or the target was renamed/removed).
3. **`name-mismatch`** (`warning`) — the declared TIA symbol doesn't match the file name (`base`).
4. **`unknown-dependency`** (`warning`) — matches no file in the family and isn't listed in either catalog.
5. **`system-dependency`** (`info`) — matches `plc-system.json`.
6. **`untracked-dependency`** (`info`) — matches `plc-untracked.json`.

## Consuming `core.json`

An edge always has exactly one of three shapes, so a consumer can branch on them without guessing:

| Shape         | `resolved` | `ambiguous` | Extra keys                |
| :------------ | :--------: | :---------: | :------------------------ |
| **resolved**  | `true`     | `false`     | —                         |
| **ambiguous** | `false`    | `true`      | `candidates`              |
| **external**  | `false`    | `false`     | `external: true`, `kind`  |

Likewise, a report always carries `level`, `type` and `message`; the rest depend on `type` — `dependency` + `usedBy` on the four `*-dependency` types, `file` + `base` + `name` on `name-mismatch`, `file` + `deprecatedBy` on `broken-deprecation`.

The [`models/`](models/) package is the definition of this contract, and what to edit when the format changes — one dataclass per module:

| Module | Class | Role |
| :--------------------------------------------- | :---------------- | :------------------------------------------ |
| [`common.py`](models/common.py)                 | —                 | The closed value sets shared by the rest.    |
| [`block_metadata.py`](models/block_metadata.py) | `BlockMetadata`   | The `TITLE` object inside a source file.     |
| [`node.py`](models/node.py)                     | `Node`            | One `.scl`/`.udt` file in the graph.         |
| [`edge.py`](models/edge.py)                     | `Edge`            | One declared dependency.                     |
| [`graph.py`](models/graph.py)                   | `Graph`           | The root object of `core.json`.              |
| [`report.py`](models/report.py)                 | `Report`          | One diagnostic.                              |

`run.py` fills those objects in and calls `to_json()`, which is what fixes the key order and decides which keys are omitted. The constructors `Edge.to_node` / `to_ambiguous` / `to_external` and `Report.about_dependency` / `name_mismatch` / `broken_deprecation` build exactly the shapes above, so no caller has to remember which fields go together. `Graph.from_json(json.load(f))` reads a graph back:

```python
import json, sys
sys.path.insert(0, "tools/dependency_graph_builder")
from models import Graph

graph = Graph.from_json(json.load(open("plc/s7-1x00/core/core.json", encoding="utf-8")))
broken = [r for r in graph.reports if r.level == "error"]
```

Consumers written in another language should mirror this package: every key listed in the tables above is always present except `version` and `deprecatedBy` on a node, which are nullable, and the per-shape keys of `Edge` and `Report`, which are absent rather than null when they don't apply.
