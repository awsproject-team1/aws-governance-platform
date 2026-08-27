"""DOCX Loader. 일반 사내규정 작성 형식을 우선 대상으로 한다.

``word/document.xml``의 문서 순서를 그대로 따라가며 제목/문단/목록/표를 구분한다.
Style 이름(``Heading 1``, ``제목 1``)과 ``outlineLvl``을 모두 본다. 사내 문서는
Style 이름을 바꿔 쓰는 경우가 많아 하나만 보면 제목 계층을 통째로 잃는다.

표는 ``gridSpan``/``vMerge``를 읽어 열 위치를 지킨다. 병합을 무시하고 셀을 이어
붙이면 열이 밀려 다른 통제 항목의 값으로 읽힌다.

라이브러리를 쓰지 않고 표준 ``zipfile`` + ``ElementTree``만 쓴다. 외부 Parser를
붙이더라도 Contract는 이 Loader 경계 그대로 유지한다.
"""

from __future__ import annotations

import io
import re
import zipfile
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

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DOCUMENT_PART = "word/document.xml"

#: "Heading 2", "heading2", "제목 2"를 같은 수준으로 본다.
_HEADING_STYLE = re.compile(r"^(?:heading|제목)(\d)$")
_TITLE_STYLE = frozenset({"title", "제목"})


class DocxLoader(DocumentLoader):
    parser_profile = "docx-ooxml-loader"
    parser_version = "1"
    supported_formats = (DocumentFormat.DOCX,)

    def load(self, content: bytes, metadata: DocumentMetadata) -> CanonicalPolicyDocument:
        body = _read_body(content)
        builder = CanonicalDocumentBuilder(
            metadata,
            parser_profile=self.parser_profile,
            parser_version=self.parser_version,
        )
        for index, element in enumerate(body, start=1):
            locator = SourceLocator.of("docx", body=index)
            if element.tag == f"{W}p":
                self._paragraph(builder, element, locator)
            elif element.tag == f"{W}tbl":
                builder.block(BlockType.TABLE, _render_table(element), locator)
        return builder.build()

    @staticmethod
    def _paragraph(
        builder: CanonicalDocumentBuilder, element: ElementTree.Element, locator: SourceLocator
    ) -> None:
        text = _paragraph_text(element)
        if not text.strip():
            return
        level = _heading_level(element)
        if level is not None:
            builder.heading(level, text, locator)
            return
        indent = _list_indent(element)
        if indent is not None:
            builder.block(BlockType.LIST_ITEM, f"{indent}- {text}", locator)
            return
        builder.block(BlockType.PARAGRAPH, text, locator)


def _read_body(content: bytes) -> ElementTree.Element:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
        if DOCUMENT_PART not in archive.namelist():
            raise ExtractionError("DOCX에 word/document.xml이 없다")
        payload = archive.read(DOCUMENT_PART)
    except zipfile.BadZipFile as exc:
        raise ExtractionError("DOCX 컨테이너를 열 수 없다") from exc

    if b"<!DOCTYPE" in payload or b"<!ENTITY" in payload:
        raise ExtractionError("DTD/Entity가 포함된 DOCX는 처리하지 않는다")
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise ExtractionError("word/document.xml을 파싱할 수 없다") from exc

    body = root.find(f"{W}body")
    if body is None:
        raise ExtractionError("DOCX 본문(w:body)이 없다")
    return body


def _paragraph_text(element: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in element.iter():
        if node.tag == f"{W}t":
            parts.append(node.text or "")
        elif node.tag == f"{W}tab":
            parts.append("\t")
        elif node.tag in (f"{W}br", f"{W}cr"):
            parts.append("\n")
    return "".join(parts).strip()


def _style_value(element: ElementTree.Element, name: str) -> str | None:
    properties = element.find(f"{W}pPr")
    if properties is None:
        return None
    node = properties.find(f"{W}{name}")
    if node is None:
        return None
    return node.get(f"{W}val")


def _heading_level(element: ElementTree.Element) -> int | None:
    style = _style_value(element, "pStyle")
    if style:
        key = re.sub(r"[\s_-]+", "", style).casefold()
        if key in _TITLE_STYLE:
            return 1
        match = _HEADING_STYLE.match(key)
        if match:
            return min(int(match.group(1)), 6)
    outline = _style_value(element, "outlineLvl")
    if outline is not None and outline.isdigit():
        level = int(outline) + 1
        if 1 <= level <= 6:
            return level
    return None


def _list_indent(element: ElementTree.Element) -> str | None:
    properties = element.find(f"{W}pPr")
    if properties is None:
        return None
    numbering = properties.find(f"{W}numPr")
    if numbering is None:
        return None
    level_node = numbering.find(f"{W}ilvl")
    raw = level_node.get(f"{W}val") if level_node is not None else "0"
    depth = int(raw) if raw and raw.isdigit() else 0
    return "  " * min(depth, 8)


def _render_table(table: ElementTree.Element) -> str:
    """표를 열 위치가 보존된 격자 문자열로 만든다."""
    grid: list[list[str]] = []
    for row in table.findall(f"{W}tr"):
        cells: list[str] = []
        for cell in row.findall(f"{W}tc"):
            span = _grid_span(cell)
            text = " ".join(
                _paragraph_text(paragraph) for paragraph in cell.findall(f"{W}p")
            ).strip()
            text = text.replace("\n", " ").replace("|", "\\|")
            if _is_merge_continuation(cell):
                text = ""
            cells.append(text)
            cells.extend([""] * (span - 1))
        grid.append(cells)
    width = max((len(row) for row in grid), default=0)
    return "\n".join("| " + " | ".join(row + [""] * (width - len(row))) + " |" for row in grid)


def _cell_properties(cell: ElementTree.Element) -> ElementTree.Element | None:
    return cell.find(f"{W}tcPr")


def _grid_span(cell: ElementTree.Element) -> int:
    properties = _cell_properties(cell)
    if properties is None:
        return 1
    node = properties.find(f"{W}gridSpan")
    raw = node.get(f"{W}val") if node is not None else None
    if raw and raw.isdigit():
        return max(1, min(int(raw), 64))
    return 1


def _is_merge_continuation(cell: ElementTree.Element) -> bool:
    """세로 병합의 이어지는 칸. 시작 칸의 값을 반복하지 않고 빈 칸으로 남긴다."""
    properties = _cell_properties(cell)
    if properties is None:
        return False
    node = properties.find(f"{W}vMerge")
    if node is None:
        return False
    return (node.get(f"{W}val") or "continue").casefold() != "restart"
