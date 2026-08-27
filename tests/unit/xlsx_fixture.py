"""Unit test용 작은 XLSX Control Matrix를 코드로 만든다."""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

SHEET_MAIN = "Controls"
SHEET_ARCHIVE = "Archive"

_OFFICE_RELATIONSHIP = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_WORKBOOK_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
)
_WORKSHEET_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
)
_SHARED_STRINGS_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"
)

_STRINGS = (
    "Access Control Matrix",
    "Control ID",
    "Requirement",
    "Owner",
    "Status",
    "IAM-001",
    "Shared accounts are prohibited.",
    "Security",
    "IAM-002",
    "Access rights are reviewed quarterly.",
    "Governance",
    "ACTIVE",
    "NET-001",
    "Ingress is restricted to approved ranges.",
    "OLD-001",
    "Legacy control kept for audit.",
    "Archive Team",
    "RETIRED",
)


def control_matrix_xlsx(*, formula_cache: str | None = "ACTIVE") -> bytes:
    workbook = _workbook_xml()
    relationships = _relationships_xml()
    main_sheet = _main_sheet_xml(formula_cache=formula_cache)
    archive_sheet = _archive_sheet_xml()

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/sharedStrings.xml", _shared_strings_xml())
        archive.writestr("xl/worksheets/sheet1.xml", main_sheet)
        archive.writestr("xl/worksheets/sheet2.xml", archive_sheet)
    return stream.getvalue()


def _content_types_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Override PartName="/xl/workbook.xml"
            ContentType="{_WORKBOOK_CONTENT_TYPE}"/>
  <Override PartName="/xl/worksheets/sheet1.xml"
            ContentType="{_WORKSHEET_CONTENT_TYPE}"/>
  <Override PartName="/xl/worksheets/sheet2.xml"
            ContentType="{_WORKSHEET_CONTENT_TYPE}"/>
  <Override PartName="/xl/sharedStrings.xml"
            ContentType="{_SHARED_STRINGS_CONTENT_TYPE}"/>
</Types>"""


def _workbook_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{SHEET_MAIN}" sheetId="1" r:id="rId1"/>
    <sheet name="{SHEET_ARCHIVE}" sheetId="2" state="hidden" r:id="rId2"/>
  </sheets>
</workbook>"""


def _relationships_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
                Type="{_OFFICE_RELATIONSHIP}/worksheet"
                Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2"
                Type="{_OFFICE_RELATIONSHIP}/worksheet"
                Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3"
                Type="{_OFFICE_RELATIONSHIP}/sharedStrings"
                Target="sharedStrings.xml"/>
</Relationships>"""


def _shared_strings_xml() -> str:
    items = "".join(f"<si><t>{escape(value)}</t></si>" for value in _STRINGS)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(_STRINGS)}" uniqueCount="{len(_STRINGS)}">{items}</sst>'
    )


def _main_sheet_xml(*, formula_cache: str | None) -> str:
    cached = f"<v>{escape(formula_cache)}</v>" if formula_cache is not None else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <cols><col min="3" max="3" hidden="1"/></cols>
  <sheetData>
    <row r="1">{_shared("A1", 0)}</row>
    <row r="2">{_header_cells(2)}</row>
    <row r="3">
      {_shared("A3", 5)}{_shared("B3", 6)}{_shared("C3", 7)}
      <c r="D3" t="str"><f>UPPER(&quot;active&quot;)</f>{cached}</c>
    </row>
    <row r="4" hidden="1">
      {_shared("A4", 8)}{_shared("B4", 9)}{_shared("C4", 10)}{_shared("D4", 11)}
    </row>
    <row r="5">
      {_shared("A5", 12)}{_shared("B5", 13)}{_shared("D5", 11)}
    </row>
  </sheetData>
  <autoFilter ref="A2:D5"/>
  <mergeCells count="2"><mergeCell ref="A1:D1"/><mergeCell ref="B5:C5"/></mergeCells>
</worksheet>"""


def _archive_sheet_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">{_header_cells(1)}</row>
    <row r="2">
      {_shared("A2", 14)}{_shared("B2", 15)}{_shared("C2", 16)}{_shared("D2", 17)}
    </row>
  </sheetData>
</worksheet>"""


def _header_cells(row: int) -> str:
    return "".join(
        _shared(f"{column}{row}", index) for column, index in zip("ABCD", range(1, 5), strict=True)
    )


def _shared(reference: str, index: int) -> str:
    return f'<c r="{reference}" t="s"><v>{index}</v></c>'
