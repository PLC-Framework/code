# Dependency graph

`run.py` builds a dependency graph between `core/` blocks (`.scl`, `.udt` and the `E*.xlsx` constant tables), reading the JSON metadata embedded in each of them. It only reads under `--root` (`plc/` by default) — it never modifies source files.

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

## Files that take part

| Kind          | Becomes a node when                                     | Where its metadata lives                                             |
| :------------ | :------------------------------------------------------ | :------------------------------------------------------------------- |
| `.scl`/`.udt` | always                                                   | the `TITLE` line, right below the declaration                        |
| `.xlsx`       | the file name starts with `E` (a TIA constant table)     | the `Constants` sheet, in the `Comment` cell of the row naming the table |

Anything else under `core/` is ignored, workbooks included: `system-v3.0.xlsx` and `jxc-alarm-list-v1.0.xlsx` are not constant tables, so they stay out of the graph.

## Metadata expected in each file

```shell
FUNCTION "_priorityQueue" : Int
TITLE = {"version":"v1.0","author":"cyanezf","family":"core/adt/priority-queue","status":"current","deprecatedBy":null,"dependencies":["priorityQueueInstanceAttributes-v1.0","MOVE_BLK_VARIANT"]}
```

In an `E*.xlsx` the same object sits in the `Constants` sheet instead — usually row 2, right under the header, with the table symbol in `Name` and the metadata in `Comment`:

| Name           | Path                       | Data Type | Value | Comment                                      |
| :------------- | :------------------------- | :-------- | :---- | :------------------------------------------- |
| `EQueueMethod` | `core\adt\queue\EQueue...` | `Bool`    | `0`   | `{"version":"v3.0","author":"cyanezf",...}`  |

The script looks that row up by content, not by a fixed position, so an extra column or an extra header row does not break it.

Every block under `core/` carries the same six keys, in that order:

| Key            | Description                                                                                                                                                     |
| :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `version`      | Version **with** the leading `v` (`"v1.0"`). Must match the `-vX.Y` suffix of the file name and, in `.scl`, the native `VERSION :` attribute — see below. |
| `author`       | Author of the block. In `.scl`, must equal the native `AUTHOR :` attribute.                                                                                     |
| `family`       | Folder path of the block as `core/<dirs>`. In `.scl`, must equal the native `FAMILY :` attribute.                                                               |
| `status`       | `"current"` (default when omitted) or `"deprecated"`.                                                                                                           |
| `deprecatedBy` | `id` of the file that replaces this one when `status` is `"deprecated"`, else `null`. Must match another file's `id` exactly, or it becomes a `broken-deprecation` report. |
| `dependencies` | Names of other blocks/UDTs it depends on. May include a version (`"_foo-v1.0"`) when several versions of the same block coexist, or just the plain name when only one exists. |

All six are read into a `BlockMetadata` (see [`models/`](models/)), but only `status`, `deprecatedBy` and `dependencies` reach `core.json`: `version`, `author` and `family` stay in the sources, and the node's `version` is derived from the file name instead. The object is read key by key with regexes rather than `json.loads`, so a hand-edited one that is not strictly valid JSON — a stray comma, a Windows path left unescaped — still yields everything it declares.

### What a source must agree on

A block says what it is in up to three places, and **every disagreement is an error**:

```shell
_queue-v3.0.scl                                   <- the file name
FUNCTION "_queue" : Int
TITLE = {"version":"v3.0","author":"cyanezf","family":"core/adt/queue", ...}
{ S7_Optimized_Access := 'TRUE' }
AUTHOR : cyanezf                                  <- the native header
FAMILY : 'core/adt/queue'
NAME : _queue
VERSION : 3.0
```

| Source  | Version                                                                  | Author and family                              |
| :------ | :----------------------------------------------------------------------- | :--------------------------------------------- |
| `.scl`  | the name's `-vX.Y`, the TITLE's `"vX.Y"` and the header's `X.Y`         | the TITLE's `author` and `family` equal the header's `AUTHOR` and `FAMILY` |
| `.udt`  | the name's `-vX.Y` and the TITLE's `"vX.Y"`                             | not checked — a `.udt` has no such header      |
| `E*.xlsx` | the name's `-vX.Y` and the metadata's `"vX.Y"`, when it has both       | not checked                                    |

- **The file name is the reference for the version**, being what the graph resolves on: the TITLE and the header are each compared with it rather than with each other, so a report names the one that is wrong. For author and family the TITLE is the reference.
- **A `.udt`'s header is not read**, even when it carries a `VERSION :` line: TIA's own number for a type is not what the core versions it by — the two in the core that had one, `mlg2proPdi-v1.0.udt` and `mlg2proPdo-v1.0.udt`, said `0.1` there beside a TITLE of `v1.0`.
- **The header is read only down to the first `VAR` section, `BEGIN` or `STRUCT`**, so a parameter called `version` is never taken for the block's own. `FAMILY`'s single quotes are taken off before comparing; nothing else is normalised — `1.0` and `1.00` are two versions.
- **A key absent on both sides agrees**; absent on one side is a `header-mismatch` whose `found` or `expected` is `null`.

## Catalogs: `plc-system.json` / `plc-untracked.json`

Each `core/` folder may contain two flat JSON arrays of names, used to classify dependencies that don't resolve to any file in that family:

- **`plc-system.json`** — Siemens/TIA system blocks (`TON_TIME`, `MC_MOVEABSOLUTE`, `TCON`, ...).
- **`plc-untracked.json`** — blocks that genuinely exist but live outside `core/` (e.g. device-specific UDTs maintained elsewhere).

A dependency matching neither is reported as `unknown-dependency` — either add it to the right catalog or treat it as a real problem (typo, missing block).

## Output

`core.json` is written whatever the run found, so every diagnostic can be read in its `reports` array. The console gets one line per family and every **error** by name; warnings and infos are counted, and read in `core.json` or the viewer:

```shell
Run
plc/s7-1x00/core: 268 nodes, 1 error, 0 warnings
  error  header-mismatch  "__jxd1_moveAbsolute-v1.1": the header says AUTHOR "aripoll", the TITLE "cyanezf".
Done
```

**The script exits with `1` when any family has an error**, and `0` otherwise — so a hook or a CI step can refuse to commit a `core.json` that describes an inconsistent core.

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
| `name`         | TIA symbol: declared on the first line (`FUNCTION "_priorityQueue"` → `_priorityQueue`), or the `Name` cell for an `E*.xlsx`. |
| `base`         | `id` with the `-vX.Y` suffix stripped. Used to resolve unversioned dependency references. |
| `version`      | Version extracted from the file name, **without** the leading `v` (`"1.0"`), or `null` if it has no `-vX.Y` suffix. |
| `status`       | `"current"` or `"deprecated"`, from `TITLE` (defaults to `"current"`).                |
| `deprecatedBy` | `id` of the file that replaces this one, or `null`.                                   |
| `file`         | Relative path to the file.                                                            |
| `dependencies` | Raw dependency list as it appears in `TITLE`.                                         |
| `interface`    | How an FB or FC is called — see below — or `null` for a UDT, a constant table, or a block whose interface could not be read. |

### Interface fields

```json
"interface": { "input": ["method"], "output": [], "inout": ["instance", "data", "buffer"], "return": "Int" }
```

| Field    | Description                                                                                          |
| :------- | :------------------------------------------------------------------------------------------------------|
| `input`  | Names in `VAR_INPUT`, in the order the block declares them.                                           |
| `output` | Names in `VAR_OUTPUT`, in declaration order.                                                          |
| `inout`  | Names in `VAR_IN_OUT`, in declaration order.                                                          |
| `return` | An FC's return type as written on its first line (`Int`, `Void`), or `null` for an FB.                |

**Names only**: writing a call needs a parameter's name and its section — `:=` for an input or an in-out, `=>` for an output — and TIA takes each parameter's type from the block being called. Only the top level is listed: a parameter declared `Struct` (or `Array[..] of Struct`) is one name to a caller, and its members are stepped over. Attributes after a name (`{InstructionName := 'DTL'; ...}`) are dropped; `VAR`, `VAR_TEMP` and `VAR CONSTANT` are not read at all.

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
| `file`               | The file involved (every type about one source file — all but the `*-dependency` ones).            |
| `base`, `name`       | The two mismatched names (`name-mismatch` reports only).                                            |
| `version`, `expected`| The version declared in the metadata and the one the file name implies (`version-mismatch` only).   |
| `attribute`, `found`, `expected` | The header attribute — `VERSION`, `AUTHOR` or `FAMILY` — what the header says, and what it had to say (`header-mismatch` only). `found` or `expected` is `null` when that side is absent. |
| `deprecatedBy`       | The dangling value (`broken-deprecation` reports only).                                             |

Report types:

1. **`ambiguous-dependency`** (`error`) — an unversioned name matches more than one file; needs a version pin.
2. **`broken-deprecation`** (`error`) — a file's `deprecatedBy` doesn't match any file's `id` (typo, or the target was renamed/removed).
3. **`missing-version`** (`error`) — an `.scl` or `.udt` whose file name has no `-vX.Y` suffix.
4. **`missing-title`** (`error`) — an `.scl` or `.udt` with no TITLE metadata, or one whose TITLE declares no `version`.
5. **`version-mismatch`** (`error`) — the `version` in the metadata doesn't match the `-vX.Y` suffix of the file name. The suffix is what the graph resolves on, so the metadata is the side that is wrong — unless the file is the one that should be renamed.
6. **`header-mismatch`** (`error`) — an `.scl`'s native `VERSION`, `AUTHOR` or `FAMILY` doesn't say what the file name and the TITLE say, or is missing. See *What a source must agree on*.
7. **`name-mismatch`** (`warning`) — the declared TIA symbol doesn't match the file name (`base`).
8. **`unknown-dependency`** (`warning`) — matches no file in the family and isn't listed in either catalog.
9. **`system-dependency`** (`info`) — matches `plc-system.json`.
10. **`untracked-dependency`** (`info`) — matches `plc-untracked.json`.
11. **`interface-unreadable`** (`warning`) — an FB or FC whose `VAR_INPUT` / `VAR_OUTPUT` / `VAR_IN_OUT` has a line the parser cannot place, or a `Struct` it cannot close. The node stays in the graph with `interface: null`: a parameter silently missing from the list would produce a call that looks right and is not, so it refuses rather than guesses.

A file's own findings come first in `reports`, ordered by file, then what only the whole graph can say.

## Consuming `core.json`

An edge always has exactly one of three shapes, so a consumer can branch on them without guessing:

| Shape         | `resolved` | `ambiguous` | Extra keys                |
| :------------ | :--------: | :---------: | :------------------------ |
| **resolved**  | `true`     | `false`     | —                         |
| **ambiguous** | `false`    | `true`      | `candidates`              |
| **external**  | `false`    | `false`     | `external: true`, `kind`  |

Likewise, a report always carries `level`, `type` and `message`; the rest depend on `type` — `dependency` + `usedBy` on the four `*-dependency` types, `file` + `base` + `name` on `name-mismatch`, `file` + `version` + `expected` on `version-mismatch`, `file` + `attribute` + `found` + `expected` on `header-mismatch`, `file` + `deprecatedBy` on `broken-deprecation`, `file` alone on `missing-version`, `missing-title` and `interface-unreadable`.

The [`models/`](models/) package is the definition of this contract, and what to edit when the format changes — one dataclass per module:

| Module | Class | Role |
| :--------------------------------------------- | :---------------- | :------------------------------------------ |
| [`common.py`](models/common.py)                 | —                 | The closed value sets shared by the rest.    |
| [`block_metadata.py`](models/block_metadata.py) | `BlockMetadata`   | The metadata object a block declares.        |
| [`interface.py`](models/interface.py)           | `BlockInterface`  | How an FB or FC is called.                   |
| [`node.py`](models/node.py)                     | `Node`            | One block file in the graph.                 |
| [`edge.py`](models/edge.py)                     | `Edge`            | One declared dependency.                     |
| [`graph.py`](models/graph.py)                   | `Graph`           | The root object of `core.json`.              |
| [`report.py`](models/report.py)                 | `Report`          | One diagnostic.                              |

Alongside them, [`xlsx.py`](xlsx.py) is a small read-only `.xlsx` reader (zip + XML, standard library only) that hands `run.py` the cells of one sheet, so reading the constant tables needs no third-party package.

`run.py` fills those objects in and calls `to_json()`, which is what fixes the key order and decides which keys are omitted. The constructors `Edge.to_node` / `to_ambiguous` / `to_external` and `Report.about_dependency` / `name_mismatch` / `version_mismatch` / `missing_version` / `missing_title` / `header_mismatch` / `broken_deprecation` / `interface_unreadable` build exactly the shapes above, so no caller has to remember which fields go together. `Graph.from_json(json.load(f))` reads a graph back:

```python
import json, sys
sys.path.insert(0, "tools/dependency_graph_builder")
from models import Graph

graph = Graph.from_json(json.load(open("plc/s7-1x00/core/core.json", encoding="utf-8")))
broken = [r for r in graph.reports if r.level == "error"]
```

Consumers written in another language should mirror this package: every key listed in the tables above is always present except `version`, `deprecatedBy` and `interface` on a node, which are nullable — `interface` is also absent from a `core.json` written before it existed, and a reader should take that as null — and the per-shape keys of `Edge` and `Report`, which are absent rather than null when they don't apply.
