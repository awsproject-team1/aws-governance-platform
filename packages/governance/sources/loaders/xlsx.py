"""XLSX Control Matrix 전용 Loader.

XLSX는 일반 정책 본문이 아니라 행/열 의미를 가진 표다. 첫 번째로 값이 두 칸 이상
있는 행을 header로 확정하고, 이후 데이터 행 하나를 header와 함께 하나의 TABLE
Block으로 만든다. 일반 heading 문서로 평탄화하지 않는다.

수식은 실행하지 않는다. OOXML에 저장된 수식 문자열과 계산 캐시값을 함께 보존하며,
캐시값이 없으면 계산한 척하지 않고 실패한다. 병합 continuation은 빈 칸으로 남기고
숨김 시트/행/열과 AutoFilter는 데이터를 누락하지 않은 채 warning으로 보고한다.
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

from ..canonical_document import (
    BlockType,
    CanonicalDocumentBuilder,
    CanonicalPolicyDocument,
    DocumentFormat,
    DocumentMetadata,
    SourceLocator,
)
from .base import DocumentLoader, ExtractionError
from .office_xml import parse_office_xml

WORKBOOK_PART = "xl/workbook.xml"
WORKBOOK_RELS_PART = "xl/_rels/workbook.xml.rels"
SHARED_STRINGS_PART = "xl/sharedStrings.xml"

MAX_MATRIX_ROWS = 10_000
MAX_MATRIX_COLUMNS = 256
MAX_MATRIX_CELLS = 100_000

_CELL_REFERENCE = re.compile(r"^\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)$")
_RANGE_REFERENCE = re.compile(
    r"^\$?([A-Za-z]{1,3})\$?([1-9][0-9]*):\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)$"
)


@dataclass(frozen=True)
class _CellValue:
    text: str
    formula: str | None = None

    @property
    def rendered(self) -> str:
        if self.formula is None:
            return self.text
        return f"[formula:={self.formula}; cached:{self.text}]"


@dataclass(frozen=True)
class _Sheet:
    name: str
    state: str
    part_name: str


class XlsxControlMatrixLoader(DocumentLoader):
    parser_profile = "xlsx-control-matrix"
    parser_version = "1"
    supported_formats = (DocumentFormat.XLSX,)

    def load(self, content: bytes, metadata: DocumentMetadata) -> CanonicalPolicyDocument:
        builder = CanonicalDocumentBuilder(
            metadata,
            parser_profile=self.parser_profile,
            parser_version=self.parser_version,
        )
        block_count = 0
        with _open_archive(content) as archive:
            shared_strings = _read_shared_strings(archive)
            sheets = _read_sheets(archive)
            for sheet in sheets:
                if sheet.state != "visible":
                    builder.warn(
                        f"XLSX 숨김 시트 '{sheet.name}'(state={sheet.state})도 "
                        "누락하지 않고 읽었다."
                    )
                block_count += self._load_sheet(archive, sheet, shared_strings, builder)
        if not block_count:
            raise ExtractionError(
                f"'{metadata.document_id}'에서 Control Matrix 데이터 행을 찾지 못했다. "
                "각 시트에는 두 개 이상의 열을 가진 header와 최소 한 개의 데이터 행이 필요하다."
            )
        return builder.build()

    @staticmethod
    def _load_sheet(
        archive: zipfile.ZipFile,
        sheet: _Sheet,
        shared_strings: tuple[str, ...],
        builder: CanonicalDocumentBuilder,
    ) -> int:
        root = _read_xml_part(archive, sheet.part_name)
        rows, hidden_rows, formula_count = _read_rows(root, shared_strings, sheet.name)
        _, merged_continuations, merged_ranges = _read_merged_ranges(root)

        if hidden_rows:
            rendered = ", ".join(str(item) for item in sorted(hidden_rows))
            builder.warn(f"XLSX 시트 '{sheet.name}'의 숨김 행({rendered})도 누락하지 않고 읽었다.")
        hidden_columns = _hidden_columns(root)
        if hidden_columns:
            builder.warn(
                f"XLSX 시트 '{sheet.name}'에 숨김 열 범위가 있다: " + ", ".join(hidden_columns)
            )
        if merged_ranges:
            builder.warn(
                f"XLSX 시트 '{sheet.name}'의 병합 범위는 시작 셀만 값을 유지했다: "
                + ", ".join(merged_ranges)
            )
        auto_filter = _auto_filter(root)
        if auto_filter:
            builder.warn(
                f"XLSX 시트 '{sheet.name}'의 AutoFilter({auto_filter})와 관계없이 "
                "모든 데이터 행을 읽었다."
            )
        if formula_count:
            builder.warn(
                f"XLSX 시트 '{sheet.name}'의 수식 {formula_count}개를 실행하지 않고 "
                "저장된 캐시값과 함께 보존했다."
            )

        for row in rows.values():
            for position in merged_continuations:
                if position[0] == row[0]:
                    row[1].pop(position[1], None)
        header_row = _find_header_row(rows, merged_continuations)
        if header_row is None:
            builder.warn(
                f"XLSX 시트 '{sheet.name}'에는 두 개 이상의 열을 가진 header가 없어 건너뛰었다."
            )
            return 0

        row_number, header_cells = header_row
        minimum_column, maximum_column, headers = _headers(
            header_cells, merged_continuations, row_number, sheet.name
        )
        skipped = [
            number for number in rows if number < row_number and _row_has_value(rows[number][1])
        ]
        if skipped:
            builder.warn(
                f"XLSX 시트 '{sheet.name}'의 header 앞 행({', '.join(map(str, skipped))})은 "
                "preamble으로 보고 데이터 항목에서 제외했다."
            )

        count = 0
        for current_row in sorted(rows):
            if current_row <= row_number:
                continue
            _, cells = rows[current_row]
            _reject_values_outside_header(
                cells,
                minimum_column,
                maximum_column,
                sheet_name=sheet.name,
                row_number=current_row,
            )
            values = [
                _cell_text(cells, column, merged_continuations, current_row)
                for column in range(minimum_column, maximum_column + 1)
            ]
            if not any(value for value in values):
                continue
            range_value = (
                f"{_column_name(minimum_column)}{current_row}:"
                f"{_column_name(maximum_column)}{current_row}"
            )
            locator = SourceLocator.of("xlsx", sheet=_locator_value(sheet.name)).child(
                range=range_value
            )
            builder.block(BlockType.TABLE, _render_row(headers, values), locator)
            count += 1
        return count


def _open_archive(content: bytes) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ExtractionError("XLSX 컨테이너를 열 수 없다") from exc
    name_list = archive.namelist()
    names = set(name_list)
    if len(names) != len(name_list):
        archive.close()
        raise ExtractionError("XLSX 컨테이너에 중복 part 이름이 있다")
    missing = [part for part in (WORKBOOK_PART, WORKBOOK_RELS_PART) if part not in names]
    if missing:
        archive.close()
        raise ExtractionError(f"XLSX 필수 part가 없다: {', '.join(missing)}")
    return archive


def _read_xml_part(archive: zipfile.ZipFile, part_name: str) -> ElementTree.Element:
    try:
        payload = archive.read(part_name)
    except KeyError as exc:
        raise ExtractionError(f"XLSX part를 찾을 수 없다: {part_name}") from exc
    return parse_office_xml(payload, part_name)


def _read_sheets(archive: zipfile.ZipFile) -> tuple[_Sheet, ...]:
    workbook = _read_xml_part(archive, WORKBOOK_PART)
    relationships = _read_relationships(archive)
    sheets: list[_Sheet] = []
    for node in workbook.iter():
        if _local_name(node.tag) != "sheet":
            continue
        name = node.get("name", "").strip()
        relationship_id = next(
            (value for key, value in node.attrib.items() if _local_name(key) == "id"), None
        )
        if not name or not relationship_id or relationship_id not in relationships:
            raise ExtractionError("XLSX workbook의 sheet relationship이 올바르지 않다")
        target = relationships[relationship_id]
        if "\\" in target or ".." in target.split("/"):
            raise ExtractionError(f"XLSX sheet part 경로가 안전하지 않다: {target}")
        if target.startswith("/"):
            part_name = posixpath.normpath(target.lstrip("/"))
        else:
            part_name = posixpath.normpath(posixpath.join("xl", target))
        if part_name.startswith("../") or not part_name.startswith("xl/"):
            raise ExtractionError(f"XLSX sheet part 경로가 안전하지 않다: {target}")
        sheets.append(
            _Sheet(name=name, state=node.get("state", "visible").casefold(), part_name=part_name)
        )
    if not sheets:
        raise ExtractionError("XLSX workbook에 sheet가 없다")
    return tuple(sheets)


def _read_relationships(archive: zipfile.ZipFile) -> dict[str, str]:
    root = _read_xml_part(archive, WORKBOOK_RELS_PART)
    relationships: dict[str, str] = {}
    for node in root:
        if _local_name(node.tag) != "Relationship":
            continue
        if node.get("TargetMode", "Internal").casefold() == "external":
            continue
        relationship_id = node.get("Id")
        target = node.get("Target")
        if relationship_id and target:
            if relationship_id in relationships:
                raise ExtractionError(
                    f"XLSX workbook relationship ID가 중복됐다: {relationship_id}"
                )
            relationships[relationship_id] = target
    return relationships


def _read_shared_strings(archive: zipfile.ZipFile) -> tuple[str, ...]:
    if SHARED_STRINGS_PART not in archive.namelist():
        return ()
    root = _read_xml_part(archive, SHARED_STRINGS_PART)
    return tuple(
        "".join(node.text or "" for node in item.iter() if _local_name(node.tag) == "t")
        for item in root
        if _local_name(item.tag) == "si"
    )


def _read_rows(
    root: ElementTree.Element, shared_strings: tuple[str, ...], sheet_name: str
) -> tuple[dict[int, tuple[int, dict[int, _CellValue]]], set[int], int]:
    rows: dict[int, tuple[int, dict[int, _CellValue]]] = {}
    hidden_rows: set[int] = set()
    formula_count = 0
    cell_count = 0
    next_row_number = 1
    for row_node in root.iter():
        if _local_name(row_node.tag) != "row":
            continue
        raw_row = row_node.get("r")
        row_number = int(raw_row) if raw_row and raw_row.isdigit() else next_row_number
        next_row_number = row_number + 1
        if row_number < 1 or row_number > MAX_MATRIX_ROWS:
            raise ExtractionError(
                f"XLSX 시트 '{sheet_name}'의 행 번호가 지원 범위를 벗어났다: {row_number}"
            )
        if row_number in rows:
            raise ExtractionError(f"XLSX 시트 '{sheet_name}'의 행 번호가 중복됐다: {row_number}")
        if _truthy(row_node.get("hidden")):
            hidden_rows.add(row_number)
        cells: dict[int, _CellValue] = {}
        next_column = 1
        for cell_node in row_node:
            if _local_name(cell_node.tag) != "c":
                continue
            cell_count += 1
            if cell_count > MAX_MATRIX_CELLS:
                raise ExtractionError(
                    f"XLSX 시트 '{sheet_name}'의 셀이 최대 {MAX_MATRIX_CELLS}개를 넘는다"
                )
            raw_reference = cell_node.get("r")
            if raw_reference:
                column, referenced_row = _parse_cell_reference(raw_reference)
                if referenced_row != row_number:
                    raise ExtractionError(f"XLSX 셀 주소와 row가 일치하지 않는다: {raw_reference}")
            else:
                column = next_column
            next_column = column + 1
            if column > MAX_MATRIX_COLUMNS:
                raise ExtractionError(
                    f"XLSX 시트 '{sheet_name}'의 열이 최대 "
                    f"{_column_name(MAX_MATRIX_COLUMNS)}열을 넘는다"
                )
            if column in cells:
                raise ExtractionError(
                    f"XLSX 시트 '{sheet_name}'의 셀이 중복됐다: {_column_name(column)}{row_number}"
                )
            value = _read_cell(cell_node, shared_strings, sheet_name, row_number, column)
            cells[column] = value
            if value.formula is not None:
                formula_count += 1
        rows[row_number] = (row_number, cells)
    return rows, hidden_rows, formula_count


def _read_cell(
    cell: ElementTree.Element,
    shared_strings: tuple[str, ...],
    sheet_name: str,
    row_number: int,
    column: int,
) -> _CellValue:
    formula_node = _child(cell, "f")
    value_node = _child(cell, "v")
    cell_type = cell.get("t", "n")
    reference = f"{_column_name(column)}{row_number}"

    formula = None
    if formula_node is not None:
        formula = (formula_node.text or "").strip()
        if not formula:
            raise ExtractionError(
                f"XLSX 시트 '{sheet_name}'의 수식 셀 {reference}에 수식 문자열이 없다. "
                "shared formula continuation은 아직 지원하지 않는다."
            )
        if value_node is None or value_node.text is None:
            raise ExtractionError(
                f"XLSX 시트 '{sheet_name}'의 수식 셀 {reference}에 계산 캐시값이 없다. "
                "수식을 계산한 척하지 않고 재계산된 workbook을 요구한다."
            )

    text = _cell_scalar(cell, value_node, cell_type, shared_strings, sheet_name, reference)
    if cell_type == "e":
        kind = "수식 캐시값" if formula is not None else "셀 값"
        raise ExtractionError(f"XLSX 시트 '{sheet_name}'의 {reference} {kind}이 오류다: {text}")
    return _CellValue(text=text, formula=formula)


def _cell_scalar(
    cell: ElementTree.Element,
    value_node: ElementTree.Element | None,
    cell_type: str,
    shared_strings: tuple[str, ...],
    sheet_name: str,
    reference: str,
) -> str:
    raw_value = value_node.text if value_node is not None and value_node.text is not None else ""
    if cell_type == "inlineStr":
        inline = _child(cell, "is")
        return (
            "".join(node.text or "" for node in inline.iter() if _local_name(node.tag) == "t")
            if inline is not None
            else ""
        )
    if cell_type == "s":
        if not raw_value.isdigit() or int(raw_value) >= len(shared_strings):
            raise ExtractionError(
                f"XLSX 시트 '{sheet_name}'의 shared string index가 올바르지 않다: {reference}"
            )
        return shared_strings[int(raw_value)]
    if cell_type == "b":
        if raw_value not in {"0", "1"}:
            raise ExtractionError(
                f"XLSX 시트 '{sheet_name}'의 boolean 값이 올바르지 않다: {reference}"
            )
        return "TRUE" if raw_value == "1" else "FALSE"
    return raw_value


def _read_merged_ranges(
    root: ElementTree.Element,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]], tuple[str, ...]]:
    starts: set[tuple[int, int]] = set()
    continuations: set[tuple[int, int]] = set()
    ranges: list[str] = []
    for node in root.iter():
        if _local_name(node.tag) != "mergeCell":
            continue
        raw = node.get("ref", "")
        match = _RANGE_REFERENCE.fullmatch(raw)
        if not match:
            raise ExtractionError(f"XLSX 병합 범위가 올바르지 않다: {raw!r}")
        start_column = _column_number(match.group(1))
        start_row = int(match.group(2))
        end_column = _column_number(match.group(3))
        end_row = int(match.group(4))
        if start_column > end_column or start_row > end_row:
            raise ExtractionError(f"XLSX 병합 범위 순서가 올바르지 않다: {raw}")
        if end_column > MAX_MATRIX_COLUMNS or end_row > MAX_MATRIX_ROWS:
            raise ExtractionError(
                f"XLSX 병합 범위가 지원 범위를 벗어났다: {raw}. "
                f"최대 {_column_name(MAX_MATRIX_COLUMNS)}{MAX_MATRIX_ROWS}"
            )
        starts.add((start_row, start_column))
        for row in range(start_row, end_row + 1):
            for column in range(start_column, end_column + 1):
                if (row, column) != (start_row, start_column):
                    continuations.add((row, column))
        ranges.append(raw.replace("$", "").upper())
    return starts, continuations, tuple(ranges)


def _find_header_row(
    rows: dict[int, tuple[int, dict[int, _CellValue]]],
    merged_continuations: set[tuple[int, int]],
) -> tuple[int, dict[int, _CellValue]] | None:
    for row_number in sorted(rows):
        cells = rows[row_number][1]
        values = [
            value.rendered
            for column, value in cells.items()
            if (row_number, column) not in merged_continuations and value.rendered.strip()
        ]
        if len(values) >= 2:
            return row_number, cells
    return None


def _headers(
    cells: dict[int, _CellValue],
    merged_continuations: set[tuple[int, int]],
    row_number: int,
    sheet_name: str,
) -> tuple[int, int, tuple[str, ...]]:
    populated_columns = [
        column
        for column, value in cells.items()
        if (row_number, column) not in merged_continuations and value.rendered.strip()
    ]
    minimum = min(populated_columns)
    maximum = max(populated_columns)
    headers = tuple(
        _cell_text(cells, column, merged_continuations, row_number)
        for column in range(minimum, maximum + 1)
    )
    if any(not header.strip() for header in headers):
        raise ExtractionError(
            f"XLSX 시트 '{sheet_name}'의 header {row_number}행에 빈 열 이름이 있다"
        )
    if len(set(headers)) != len(headers):
        raise ExtractionError(
            f"XLSX 시트 '{sheet_name}'의 header {row_number}행에 중복 열 이름이 있다"
        )
    if any(value.formula is not None for value in cells.values()):
        raise ExtractionError(
            f"XLSX 시트 '{sheet_name}'의 header {row_number}행에는 수식을 사용할 수 없다"
        )
    return minimum, maximum, headers


def _reject_values_outside_header(
    cells: dict[int, _CellValue],
    minimum: int,
    maximum: int,
    *,
    sheet_name: str,
    row_number: int,
) -> None:
    outside = [
        column
        for column, value in cells.items()
        if (column < minimum or column > maximum) and value.rendered.strip()
    ]
    if outside:
        references = ", ".join(f"{_column_name(column)}{row_number}" for column in outside)
        raise ExtractionError(
            f"XLSX 시트 '{sheet_name}'의 데이터가 header 범위 밖에 있다: {references}"
        )


def _cell_text(
    cells: dict[int, _CellValue],
    column: int,
    merged_continuations: set[tuple[int, int]],
    row_number: int,
) -> str:
    if (row_number, column) in merged_continuations:
        return ""
    value = cells.get(column)
    return value.rendered if value is not None else ""


def _render_row(headers: tuple[str, ...], values: list[str]) -> str:
    return _render_table_line(headers) + "\n" + _render_table_line(values)


def _render_table_line(values: tuple[str, ...] | list[str]) -> str:
    escaped = [
        value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>") for value in values
    ]
    return "| " + " | ".join(escaped) + " |"


def _row_has_value(cells: dict[int, _CellValue]) -> bool:
    return any(value.rendered.strip() for value in cells.values())


def _hidden_columns(root: ElementTree.Element) -> tuple[str, ...]:
    ranges: list[str] = []
    for node in root.iter():
        if _local_name(node.tag) != "col" or not _truthy(node.get("hidden")):
            continue
        minimum = node.get("min", "")
        maximum = node.get("max", "")
        if minimum.isdigit() and maximum.isdigit():
            ranges.append(f"{_column_name(int(minimum))}:{_column_name(int(maximum))}")
        else:
            ranges.append(f"{minimum}:{maximum}")
    return tuple(ranges)


def _auto_filter(root: ElementTree.Element) -> str | None:
    return next(
        (
            node.get("ref")
            for node in root.iter()
            if _local_name(node.tag) == "autoFilter" and node.get("ref")
        ),
        None,
    )


def _parse_cell_reference(reference: str) -> tuple[int, int]:
    match = _CELL_REFERENCE.fullmatch(reference)
    if not match:
        raise ExtractionError(f"XLSX 셀 주소가 올바르지 않다: {reference!r}")
    return _column_number(match.group(1)), int(match.group(2))


def _column_number(name: str) -> int:
    value = 0
    for character in name.upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def _column_name(number: int) -> str:
    if number < 1:
        raise ExtractionError(f"XLSX 열 번호가 올바르지 않다: {number}")
    value = number
    characters: list[str] = []
    while value:
        value, remainder = divmod(value - 1, 26)
        characters.append(chr(ord("A") + remainder))
    return "".join(reversed(characters))


def _truthy(value: str | None) -> bool:
    return bool(value and value.casefold() in {"1", "true"})


def _child(element: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next((node for node in element if _local_name(node.tag) == name), None)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _locator_value(value: str) -> str:
    """SourceLocator 구분자와 충돌하는 sheet 문자를 percent encoding한다."""
    return (
        value.replace("%", "%25")
        .replace("=", "%3D")
        .replace("/", "%2F")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )
