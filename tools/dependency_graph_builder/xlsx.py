"""Minimal read-only .xlsx reader, standard library only.

An .xlsx is a zip of XML parts; this pulls the cells of one sheet out of it
so run.py can read the constant tables without pulling in openpyxl. Values
come back as the strings Excel stored, with no type conversion — enough for
the metadata and names the graph needs, not a general spreadsheet reader.
"""
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

CELL_REF_RE = re.compile(r"^([A-Z]+)")


class XlsxError(Exception):
    """The file is not a readable .xlsx, or lacks the part being asked for."""


def column_index(cell_ref: str) -> int:
    """Column number of a cell reference, 1-based: A -> 1, B -> 2, AA -> 27."""
    letters = CELL_REF_RE.match(cell_ref)
    if not letters:
        raise XlsxError(f"unexpected cell reference {cell_ref!r}")
    index = 0
    for char in letters.group(1):
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index


def _text_of(element) -> str:
    """Concatenate every <t> under an element, as Excel splits runs of text."""
    return "".join(t.text or "" for t in element.iter(f"{{{MAIN_NS}}}t"))


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [_text_of(si) for si in root.findall(f"{{{MAIN_NS}}}si")]


def _sheet_parts(archive: zipfile.ZipFile) -> dict[str, str]:
    """{sheet name: zip path}, in workbook order."""
    rels = {
        rel.get("Id"): rel.get("Target")
        for rel in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    }
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    sheets = {}
    for sheet in workbook.find(f"{{{MAIN_NS}}}sheets"):
        target = rels.get(sheet.get(f"{{{DOC_REL_NS}}}id"))
        if target:
            sheets[sheet.get("name")] = "xl/" + target.lstrip("/").removeprefix("xl/")
    return sheets


def sheet_names(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            return list(_sheet_parts(archive))
    except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError, TypeError) as exc:
        raise XlsxError(f"{path}: {exc}") from exc


def sheet_rows(path: Path, sheet: str) -> dict[int, dict[int, str]]:
    """{row number: {column number: cell text}}, both 1-based, empty cells absent.

    Raises XlsxError if the file cannot be read or has no such sheet.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            parts = _sheet_parts(archive)
            if sheet not in parts:
                raise XlsxError(f'{path}: no sheet named "{sheet}"')
            strings = _shared_strings(archive)
            root = ET.fromstring(archive.read(parts[sheet]))
    except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError, TypeError) as exc:
        raise XlsxError(f"{path}: {exc}") from exc

    rows: dict[int, dict[int, str]] = {}
    data = root.find(f"{{{MAIN_NS}}}sheetData")
    if data is None:
        return rows

    for row in data.findall(f"{{{MAIN_NS}}}row"):
        cells: dict[int, str] = {}
        for cell in row.findall(f"{{{MAIN_NS}}}c"):
            ref = cell.get("r")
            if not ref:
                continue
            kind = cell.get("t")
            value = cell.find(f"{{{MAIN_NS}}}v")
            if kind == "inlineStr":
                inline = cell.find(f"{{{MAIN_NS}}}is")
                text = _text_of(inline) if inline is not None else ""
            elif kind == "s" and value is not None:
                try:
                    text = strings[int(value.text)]
                except (ValueError, IndexError):
                    text = ""
            else:
                text = value.text if value is not None and value.text else ""
            if text:
                cells[column_index(ref)] = text
        if cells:
            rows[int(row.get("r"))] = cells
    return rows
