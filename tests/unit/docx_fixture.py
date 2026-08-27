"""Test용 최소 DOCX 생성기.

Binary Fixture를 Repository에 커밋하면 Review에서 내용을 볼 수 없다. 대신 검토 가능한
코드로 같은 바이트를 결정론적으로 만든다. Word가 만드는 문서의 부분집합이지만 이
Loader가 읽는 요소(Style 기반 제목, outlineLvl, numPr 목록, gridSpan/vMerge 표)는
모두 포함한다.
"""

from __future__ import annotations

import io
import zipfile

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package'
    '.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)

RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)


def paragraph(
    text: str,
    *,
    style: str | None = None,
    outline: int | None = None,
    list_level: int | None = None,
) -> str:
    properties = ""
    if style is not None:
        properties += f'<w:pStyle w:val="{style}"/>'
    if outline is not None:
        properties += f'<w:outlineLvl w:val="{outline}"/>'
    if list_level is not None:
        properties += f'<w:numPr><w:ilvl w:val="{list_level}"/><w:numId w:val="1"/></w:numPr>'
    prefix = f"<w:pPr>{properties}</w:pPr>" if properties else ""
    return f'<w:p>{prefix}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def cell(text: str, *, grid_span: int | None = None, v_merge: str | None = None) -> str:
    properties = ""
    if grid_span is not None:
        properties += f'<w:gridSpan w:val="{grid_span}"/>'
    if v_merge is not None:
        properties += f'<w:vMerge w:val="{v_merge}"/>' if v_merge else "<w:vMerge/>"
    prefix = f"<w:tcPr>{properties}</w:tcPr>" if properties else ""
    return f"<w:tc>{prefix}{paragraph(text)}</w:tc>"


def row(*cells: str) -> str:
    return "<w:tr>" + "".join(cells) + "</w:tr>"


def table(*rows: str) -> str:
    return "<w:tbl>" + "".join(rows) + "</w:tbl>"


def build_docx(body: str) -> bytes:
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W}><w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELS)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


#: 사내규정 형태의 기본 Fixture. 제목/목록/표/중복 제목을 모두 포함한다.
GOLDEN_BODY = "".join(
    [
        paragraph("접근 통제 규정", style="Heading1"),
        paragraph("이 규정은 계정과 권한의 최소 기준을 정한다."),
        paragraph("제1조 계정 관리", style="제목 2"),
        paragraph("공용 계정을 사용하지 않는다.", list_level=0),
        paragraph("불가피한 경우 승인 기록을 남긴다.", list_level=1),
        paragraph("제2조 권한 검토", outline=1),
        table(
            row(cell("구분"), cell("주기"), cell("책임")),
            row(cell("정기 검토", v_merge="restart"), cell("분기 1회"), cell("정보보안팀")),
            row(cell("", v_merge=""), cell("상시 점검", grid_span=2)),
        ),
        paragraph("제1조 계정 관리", style="제목 2"),
        paragraph("같은 제목이 반복되는 경우를 포함한다."),
    ]
)


def golden_docx() -> bytes:
    return build_docx(GOLDEN_BODY)
