"""텍스트 PDF Loader.

PDF 원문 바이트의 ``/Font``/``/Image`` marker만 검색하면 압축 Object Stream을
판별하지 못한다. 이 Loader는 pypdf로 실제 객체를 연 뒤 페이지별 텍스트 계층과
이미지 XObject를 확인한다.

텍스트 조각은 렌더링 좌표로 줄과 문단을 재구성하고 ``pdf:page=N/block=M``
locator를 남긴다. PDF에는 heading semantic이 없는 경우가 많으므로 본문보다 큰
글꼴을 결정론적으로 heading으로 분류한다. 글꼴 크기로 heading을 찾을 수 없는
문서는 빈 결과가 아니라 이후 CanonicalHeadingProfile에서 명시적으로 실패한다.

이미지 전용 페이지가 텍스트 페이지와 섞인 경우에도 일부 페이지만 조용히
수집하지 않는다. OCR 없이는 문서 전체를 보존할 수 없으므로 OcrRequiredError로
보낸다.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

from ..canonical_document import (
    BlockType,
    CanonicalDocumentBuilder,
    CanonicalPolicyDocument,
    DocumentFormat,
    DocumentMetadata,
    SourceLocator,
)
from .base import DocumentLoader, ExtractionError, OcrRequiredError

MAX_PDF_PAGES = 500
MAX_EXTRACTED_CHARACTERS = 2_000_000


class PdfKind(str, Enum):
    TEXT = "TEXT"
    SCANNED = "SCANNED"
    ENCRYPTED = "ENCRYPTED"
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True)
class _TextFragment:
    text: str
    x: float
    y: float
    font_size: float


@dataclass(frozen=True)
class _PdfLine:
    text: str
    x: float
    y: float
    font_size: float


@dataclass(frozen=True)
class _PdfBlock:
    text: str
    font_size: float


@dataclass(frozen=True)
class _PageAnalysis:
    lines: tuple[_PdfLine, ...]
    has_image: bool


@dataclass(frozen=True)
class _PdfAnalysis:
    encrypted: bool
    pages: tuple[_PageAnalysis, ...]

    @property
    def has_text(self) -> bool:
        return any(page.lines for page in self.pages)

    @property
    def has_image(self) -> bool:
        return any(page.has_image for page in self.pages)

    @property
    def image_only_pages(self) -> tuple[int, ...]:
        return tuple(
            index
            for index, page in enumerate(self.pages, start=1)
            if page.has_image and not page.lines
        )


def classify_pdf(content: bytes) -> PdfKind:
    """실제 PDF 객체를 열어 텍스트/스캔/암호화 상태를 판별한다.

    pypdf가 Object Stream을 해제한 뒤 ``extract_text``를 실행하므로 ``/Font``가
    압축 객체 안에 있어도 원문 marker 검색처럼 ``UNDETERMINED``로 빠지지 않는다.
    """
    analysis = _analyze_pdf(content)
    if analysis.encrypted:
        return PdfKind.ENCRYPTED
    if analysis.has_text:
        return PdfKind.TEXT
    if analysis.has_image:
        return PdfKind.SCANNED
    return PdfKind.UNDETERMINED


class PdfTriageLoader(DocumentLoader):
    """텍스트 PDF를 Canonical Block으로 변환하고 OCR 필요 문서를 분리한다."""

    parser_profile = "pdf-triage"
    parser_version = "2"
    supported_formats = (DocumentFormat.PDF,)

    def load(self, content: bytes, metadata: DocumentMetadata) -> CanonicalPolicyDocument:
        analysis = _analyze_pdf(content)
        if analysis.encrypted:
            raise ExtractionError(
                f"'{metadata.document_id}'는 암호화된 PDF다. 해제된 사본을 다시 업로드해야 한다."
            )

        image_only_pages = analysis.image_only_pages
        if image_only_pages:
            pages = ", ".join(str(page) for page in image_only_pages)
            raise OcrRequiredError(
                f"'{metadata.document_id}'의 PDF {pages}페이지에는 텍스트 계층이 없다. "
                "일부 페이지를 누락하지 않고 OCR Adapter와 Human Review 경로로 보낸다."
            )
        if not analysis.has_text:
            if analysis.has_image:
                raise OcrRequiredError(
                    f"'{metadata.document_id}'는 텍스트 계층이 없는 스캔 PDF다. "
                    "빈 문서로 처리하지 않고 OCR Adapter와 Human Review 경로로 보낸다."
                )
            raise ExtractionError(
                f"'{metadata.document_id}'에서 텍스트 계층을 찾지 못했다. "
                "빈 문서로 처리하지 않고 PDF 구조를 확인해야 한다."
            )

        builder = CanonicalDocumentBuilder(
            metadata,
            parser_profile=self.parser_profile,
            parser_version=self.parser_version,
        )
        all_lines = tuple(line for page in analysis.pages for line in page.lines)
        body_size = _body_font_size(all_lines)
        heading_sizes = _heading_sizes(all_lines, body_size)

        for page_number, page in enumerate(analysis.pages, start=1):
            if not page.lines:
                builder.warn(f"PDF {page_number}페이지는 텍스트가 없는 빈 페이지라 건너뛰었다.")
                continue
            for block_number, block in enumerate(
                _logical_blocks(page.lines, heading_sizes), start=1
            ):
                locator = SourceLocator.of("pdf", page=page_number).child(block=block_number)
                level = _heading_level(block, heading_sizes)
                if level is None:
                    builder.block(BlockType.PARAGRAPH, block.text, locator)
                else:
                    builder.heading(level, block.text, locator)

        builder.warn(
            "PDF의 읽기 순서는 시각 좌표로 재구성했다. 다단 편집과 표는 원문 대조가 필요하다."
        )
        return builder.build()


def _analyze_pdf(content: bytes) -> _PdfAnalysis:
    if not content.startswith(b"%PDF-"):
        raise ExtractionError("PDF signature가 없다")
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
    except (PdfReadError, ValueError, TypeError) as exc:
        raise ExtractionError("PDF 객체를 파싱할 수 없다") from exc

    if reader.is_encrypted:
        return _PdfAnalysis(encrypted=True, pages=())
    try:
        page_count = len(reader.pages)
    except (FileNotDecryptedError, PdfReadError, ValueError) as exc:
        raise ExtractionError("PDF 페이지 트리를 읽을 수 없다") from exc
    if page_count > MAX_PDF_PAGES:
        raise ExtractionError(f"PDF 페이지가 최대 {MAX_PDF_PAGES}개를 넘는다")

    pages: list[_PageAnalysis] = []
    extracted_characters = 0
    try:
        for page in reader.pages:
            fragments = _extract_fragments(page)
            lines = _lines_from_fragments(fragments)
            extracted_characters += sum(len(line.text) for line in lines)
            if extracted_characters > MAX_EXTRACTED_CHARACTERS:
                raise ExtractionError(
                    f"PDF 추출 문자열이 최대 {MAX_EXTRACTED_CHARACTERS}자를 넘는다"
                )
            pages.append(_PageAnalysis(lines=lines, has_image=_page_has_image(page)))
    except ExtractionError:
        raise
    except (FileNotDecryptedError, PdfReadError, TypeError, ValueError) as exc:
        raise ExtractionError("PDF 페이지의 텍스트 계층을 추출할 수 없다") from exc
    return _PdfAnalysis(encrypted=False, pages=tuple(pages))


def _extract_fragments(page: Any) -> tuple[_TextFragment, ...]:
    fragments: list[_TextFragment] = []

    def visitor(
        text: str,
        current_matrix: list[float],
        text_matrix: list[float],
        _font: dict[str, Any] | None,
        font_size: float,
    ) -> None:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if not normalized.strip():
            return
        x, y = _position(current_matrix, text_matrix)
        effective_size = abs(float(font_size)) * _vertical_scale(current_matrix)
        parts = normalized.split("\n")
        for offset, part in enumerate(parts):
            value = " ".join(part.split())
            if value:
                fragments.append(
                    _TextFragment(
                        text=value,
                        x=x,
                        y=y - offset * max(effective_size, 1.0),
                        font_size=effective_size,
                    )
                )

    page.extract_text(visitor_text=visitor)
    return tuple(fragments)


def _position(current_matrix: list[float], text_matrix: list[float]) -> tuple[float, float]:
    """Text matrix 위치에 current transformation matrix를 적용한다."""
    x = float(text_matrix[4])
    y = float(text_matrix[5])
    return (
        x * float(current_matrix[0]) + y * float(current_matrix[2]) + float(current_matrix[4]),
        x * float(current_matrix[1]) + y * float(current_matrix[3]) + float(current_matrix[5]),
    )


def _vertical_scale(matrix: list[float]) -> float:
    return max(math.hypot(float(matrix[2]), float(matrix[3])), 0.01)


def _lines_from_fragments(fragments: tuple[_TextFragment, ...]) -> tuple[_PdfLine, ...]:
    """가까운 y 좌표의 조각을 한 visual line으로 묶는다."""
    ordered = sorted(fragments, key=lambda item: (-item.y, item.x, item.text))
    groups: list[list[_TextFragment]] = []
    for fragment in ordered:
        if not groups:
            groups.append([fragment])
            continue
        group = groups[-1]
        baseline = sum(item.y for item in group) / len(group)
        tolerance = max(1.5, max(item.font_size for item in group) * 0.35)
        if abs(fragment.y - baseline) <= tolerance:
            group.append(fragment)
        else:
            groups.append([fragment])

    lines: list[_PdfLine] = []
    for group in groups:
        group.sort(key=lambda item: (item.x, item.text))
        text = _join_fragments(group)
        if text:
            lines.append(
                _PdfLine(
                    text=text,
                    x=min(item.x for item in group),
                    y=sum(item.y for item in group) / len(group),
                    font_size=max(item.font_size for item in group),
                )
            )
    return tuple(lines)


def _join_fragments(fragments: list[_TextFragment]) -> str:
    result = ""
    for fragment in fragments:
        if not result:
            result = fragment.text
        elif result.endswith((" ", "-", "/", "(")) or fragment.text.startswith(
            (" ", ".", ",", ";", ":", ")", "]")
        ):
            result += fragment.text
        else:
            result += " " + fragment.text
    return result.strip()


def _body_font_size(lines: tuple[_PdfLine, ...]) -> float:
    """문자 수 가중 중앙값. 짧고 큰 제목이 본문 크기를 지배하지 않게 한다."""
    weighted = sorted((line.font_size, max(len(line.text), 1)) for line in lines)
    total = sum(weight for _, weight in weighted)
    threshold = total / 2
    seen = 0
    for size, weight in weighted:
        seen += weight
        if seen >= threshold:
            return size
    return weighted[-1][0] if weighted else 0.0


def _heading_sizes(lines: tuple[_PdfLine, ...], body_size: float) -> tuple[float, ...]:
    if body_size <= 0:
        return ()
    sizes = {
        round(line.font_size, 2)
        for line in lines
        if line.font_size >= body_size * 1.18 and len(line.text) <= 200
    }
    return tuple(sorted(sizes, reverse=True)[:6])


def _heading_level(block: _PdfBlock, heading_sizes: tuple[float, ...]) -> int | None:
    rounded = round(block.font_size, 2)
    try:
        return heading_sizes.index(rounded) + 1
    except ValueError:
        return None


def _logical_blocks(
    lines: tuple[_PdfLine, ...], heading_sizes: tuple[float, ...]
) -> tuple[_PdfBlock, ...]:
    """heading은 단독 Block, 가까운 본문 줄은 한 문단 Block으로 묶는다."""
    blocks: list[_PdfBlock] = []
    paragraph: list[_PdfLine] = []

    def flush() -> None:
        if not paragraph:
            return
        blocks.append(
            _PdfBlock(
                text="\n".join(line.text for line in paragraph),
                font_size=max(line.font_size for line in paragraph),
            )
        )
        paragraph.clear()

    for line in lines:
        is_heading = round(line.font_size, 2) in heading_sizes
        if is_heading:
            flush()
            blocks.append(_PdfBlock(text=line.text, font_size=line.font_size))
            continue
        if paragraph:
            previous = paragraph[-1]
            vertical_gap = previous.y - line.y
            close = vertical_gap <= max(previous.font_size, line.font_size) * 1.8
            aligned = abs(previous.x - line.x) <= max(24.0, line.font_size * 2.5)
            if not close or not aligned:
                flush()
        paragraph.append(line)
    flush()
    return tuple(blocks)


def _page_has_image(page: Any) -> bool:
    resources = _resolve(page.get("/Resources"))
    return _resources_have_image(resources, seen=set(), depth=0)


def _resources_have_image(resources: Any, *, seen: set[int], depth: int) -> bool:
    if not isinstance(resources, dict) or depth > 8:
        return False
    xobjects = _resolve(resources.get("/XObject"))
    if not isinstance(xobjects, dict):
        return False
    for reference in xobjects.values():
        item = _resolve(reference)
        marker = id(item)
        if marker in seen or not isinstance(item, dict):
            continue
        seen.add(marker)
        subtype = str(item.get("/Subtype", ""))
        if subtype == "/Image":
            return True
        if subtype == "/Form" and _resources_have_image(
            _resolve(item.get("/Resources")), seen=seen, depth=depth + 1
        ):
            return True
    return False


def _resolve(value: Any) -> Any:
    getter = getattr(value, "get_object", None)
    return getter() if callable(getter) else value
