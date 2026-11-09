"""ALH-223 (M2-04.2) — XLSX workbooks a test can state in words, not commit as bytes.

Two helpers, because the two jobs are different. ``workbook_bytes`` writes the OOXML by hand
(stdlib ``zipfile`` and strings) so a test can say *this cell is a formula with no stored value*
and *this row is blank* — the two things openpyxl will not write for you and the two things the
import's promises are about. ``xlsx_from_csv`` uses openpyxl to save the forty-row CSV fixture as
a workbook, so the equivalence claim compares the same values in both formats and cannot drift
from the file it is paired with.

Nothing here is a test: the module has no ``test_`` prefix, so pytest imports it only when asked.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


@dataclass
class Formula:
    """A cell that holds a formula, and possibly the value a spreadsheet last stored for it.

    ``cached=None`` is the case the import must see: a formula nobody recalculated, which reads
    as empty to anything that asks for a value and cannot be computed here.
    """

    text: str
    cached: Any = None


def column_letter(index: int) -> str:
    """The spreadsheet's own name for a 1-based column: 1 is ``A``, 27 is ``AA``."""
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _xml(value: object) -> str:
    if isinstance(value, bool):
        return escape("TRUE" if value else "FALSE")
    if isinstance(value, (int, float)):
        return repr(value)
    return escape(str(value))


def _cell(address: str, value: object) -> str:
    if isinstance(value, Formula):
        stored = "" if value.cached is None else f"<v>{_xml(value.cached)}</v>"
        return f'<c r="{address}"><f>{escape(value.text.lstrip("="))}</f>{stored}</c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{address}"><v>{_xml(value)}</v></c>'
    text = "" if value is None else str(value)
    return f'<c r="{address}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'


def _sheet_xml(rows: Sequence[Sequence[object] | None]) -> str:
    parts: list[str] = []
    for number, row in enumerate(rows, start=1):
        if row is None:
            continue  # a blank sheet row: no <row> element, and openpyxl pads it back as empties
        cells = "".join(
            _cell(f"{column_letter(index)}{number}", value)
            for index, value in enumerate(row, start=1)
            if value is not None
        )
        parts.append(f'<row r="{number}">{cells}</row>')
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{_MAIN_NS}"><sheetData>{"".join(parts)}</sheetData></worksheet>'
    )


def workbook_bytes(sheets: Mapping[str, Sequence[Sequence[object] | None]]) -> bytes:
    """The bytes of a workbook with one named sheet per entry, in the order given."""
    names = list(sheets)
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(names) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{overrides}</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_REL_NS}">'
        f'<Relationship Id="rId1" Type="{_DOC_REL_NS}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    sheet_entries = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(names, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{_MAIN_NS}" xmlns:r="{_DOC_REL_NS}">'
        f"<sheets>{sheet_entries}</sheets></workbook>"
    )
    workbook_rels_entries = "".join(
        f'<Relationship Id="rId{index}" Type="{_DOC_REL_NS}/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(names) + 1)
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_REL_NS}">{workbook_rels_entries}</Relationships>'
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for index, name in enumerate(names, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(sheets[name]))
    return buffer.getvalue()


def xlsx_from_csv(text: str, sheet: str = "Outcomes") -> bytes:
    """The workbook a person would have saved instead of this CSV.

    A cell whose text is a number is written as a number, because that is what "Save as" does, and
    the equivalence claim is then about the same values arriving by two routes rather than the same
    strings. Requires the ``xlsx`` extra; the tests that call it are the present-extra path.
    """
    import openpyxl

    book = openpyxl.Workbook()
    worksheet = book.active
    worksheet.title = sheet
    for row in csv.reader(io.StringIO(text, newline="")):
        worksheet.append([_as_spreadsheet_value(cell) for cell in row])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _as_spreadsheet_value(cell: str) -> Any:
    if not cell.strip():
        return None
    try:
        return float(cell)
    except ValueError:
        return cell
