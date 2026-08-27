"""문서 비종속 Ingestion 경계.

Pipeline::

    load -> [segment] -> normalize -> anchor -> hash -> emit

``load``는 형식별 Document Loader가, ``segment``는 교체 가능한 Structure Profile이
담당한다. 나머지 단계는 어떤 사내 규정 문서가 들어와도 동일하게 동작하는 결정론적
코드다. 이 분리가 없으면 문서 형식마다 정규화·해시 규칙이 갈라져 Source별 Score
비교가 성립하지 않는다.

Profile은 이제 원문 문자열이 아니라 :class:`CanonicalPolicyDocument`를 입력으로 받는다.
DOCX 표, XLSX 셀, PDF 페이지, HTML DOM 위치를 문자열로 평탄화하기 전에 Block으로
보존해야 Evidence가 원문 위치를 가리킬 수 있기 때문이다.

이 모듈은 ``packages.contracts``에 새 Contract를 만들지 않는다. Policy Source의 상세
metadata와 관리 API Schema는 docs/CONTRACTS.md에서 Open Decision이므로, 여기서는 이미
확정된 ``SourceReference``(document_id + document_version + section + content_hash)를
생성하는 것까지만 담당한다. Block locator는 Contract가 아니라 안정적인 문자열로
``DocumentSection.locator``에 실어 Evidence가 쓰게 한다.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from urllib.parse import unquote

from ..errors import GovernanceValidationError
from .canonical_document import (
    BlockType,
    CanonicalBlock,
    CanonicalPolicyDocument,
    DocumentFormat,
    render_blocks,
    resolve_format,
)
from .loaders import TEXT_FORMATS, load_text_document
from .normalization import content_hash, normalize_for_hash, slugify

__all__ = [
    "CanonicalHeadingProfile",
    "DocumentSection",
    "ExtractionMethod",
    "LlmSegmentationProfile",
    "SegmentConfidence",
    "SegmentationError",
    "SegmentationNotImplementedError",
    "SegmentationResult",
    "StructureProfile",
    "UnsupportedDocumentError",
    "XlsxControlMatrixProfile",
    "content_hash",
    "normalize_for_hash",
    "slugify",
]


class ExtractionMethod(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"
    MANUAL = "MANUAL"


class SegmentConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


#: HIGH가 아닌 항목은 Rule Candidate로 넘기기 전에 사람이 확인해야 한다.
REVIEW_REQUIRED_CONFIDENCE = frozenset({SegmentConfidence.MEDIUM, SegmentConfidence.LOW})


class SegmentationError(GovernanceValidationError):
    """문서를 항목으로 쪼갤 수 없을 때. 조용한 빈 결과 대신 이 예외를 쓴다."""


class UnsupportedDocumentError(SegmentationError):
    """Profile이 이 문서 구조를 인식하지 못했다."""


class SegmentationNotImplementedError(SegmentationError):
    """Profile 자체가 아직 구현되지 않았다.

    미구현을 성공으로 위장하지 않기 위해 존재한다. 항목 0개를 조용히 돌려주면
    "업로드는 됐는데 Rule이 안 나온다"가 되어 어디서 막혔는지 드러나지 않는다.
    """


@dataclass(frozen=True)
class DocumentSection:
    """원문 한 항목. ``section``이 Evidence가 참조할 안정적 주소다.

    ``locator``는 같은 항목의 원문 위치(Markdown 줄, DOCX 본문 위치, HTML DOM 경로)를
    가리키는 문자열이다. ``section`` anchor는 Contract 값이고 ``locator``는 사람이
    원문을 다시 열 때 쓰는 보조 주소다.
    """

    section: str
    heading_path: tuple[str, ...]
    raw_block: str
    confidence: SegmentConfidence
    locator: str = ""
    block_ids: tuple[str, ...] = ()

    @property
    def content_hash(self) -> str:
        return content_hash(self.raw_block)

    @property
    def review_required(self) -> bool:
        return self.confidence in REVIEW_REQUIRED_CONFIDENCE


@dataclass(frozen=True)
class SegmentationResult:
    profile_id: str
    profile_version: str
    method: ExtractionMethod
    sections: tuple[DocumentSection, ...]

    def __post_init__(self) -> None:
        anchors = [item.section for item in self.sections]
        if len(set(anchors)) != len(anchors):
            raise SegmentationError("section anchor가 문서 안에서 중복됐다")


class StructureProfile(ABC):
    """Canonical Block을 항목으로 묶는 교체 가능한 단계.

    Profile이 하는 것: 항목 경계를 찾고 heading 계층과 원문 구간을 채운다.
    Profile이 하지 않는 것: 파일 형식 판별, 해시 계산, 동결 검증,
    control_key/severity/evaluation_type 결정.
    """

    profile_id: str
    profile_version: str
    method: ExtractionMethod
    supported_formats: tuple[DocumentFormat, ...] = ()

    def supports(self, document_type: str) -> bool:
        detected = resolve_format(document_type)
        return detected is not None and detected in self.supported_formats

    @abstractmethod
    def segment_document(self, document: CanonicalPolicyDocument) -> SegmentationResult:
        raise NotImplementedError

    def segment(self, raw_text: str, document_type: str) -> SegmentationResult:
        """원문 문자열 경로. 업로드 파일은 Loader를 거쳐 ``segment_document``로 온다."""
        detected = resolve_format(document_type)
        if detected is None or not self.supports(document_type) or detected not in TEXT_FORMATS:
            raise UnsupportedDocumentError(
                f"{self.profile_id} profile의 원문 문자열 경로는 "
                f"'{document_type}' 문서를 처리하지 않는다"
            )
        document = load_text_document(
            raw_text,
            detected,
            document_id="inline-text",
            document_version="inline-text",
        )
        return self.segment_document(document)


class CanonicalHeadingProfile(StructureProfile):
    """Canonical Document를 heading 계층으로 쪼개는 결정론적 기본 Profile.

    특정 사내 문서의 서식을 가정하지 않는다. Loader가 표시한 heading Block만 항목
    경계로 쓰므로 Markdown의 ``#``, DOCX의 ``Heading``/``제목`` Style, HTML의 ``h1``이
    모두 같은 규칙으로 처리된다. 결정론적이라 같은 원문은 항상 같은 anchor와 해시를 만든다.
    """

    profile_id = "canonical-heading"
    profile_version = "1"
    method = ExtractionMethod.DETERMINISTIC
    supported_formats = (
        DocumentFormat.MARKDOWN,
        DocumentFormat.TXT,
        DocumentFormat.HTML,
        DocumentFormat.DOCX,
        DocumentFormat.PDF,
    )

    def segment_document(self, document: CanonicalPolicyDocument) -> SegmentationResult:
        if document.detected_format not in self.supported_formats:
            raise UnsupportedDocumentError(
                f"{self.profile_id} profile은 '{document.detected_format.value}' 문서를 "
                "처리하지 않는다"
            )
        starts = [
            index
            for index, block in enumerate(document.blocks)
            if block.block_type is BlockType.HEADING
        ]
        if not starts:
            raise UnsupportedDocumentError(
                "제목 구조가 없어 항목 경계를 찾을 수 없다. 다른 Structure Profile이 필요하다."
            )

        sections: list[DocumentSection] = []
        used: dict[str, int] = {}
        for order, start in enumerate(starts):
            end = starts[order + 1] if order + 1 < len(starts) else len(document.blocks)
            blocks = document.blocks[start:end]
            heading = blocks[0]
            anchor = _anchor(heading, order, used)
            sections.append(
                DocumentSection(
                    section=anchor,
                    heading_path=heading.heading_path,
                    raw_block=render_blocks(blocks),
                    confidence=SegmentConfidence.HIGH,
                    locator=heading.locator.canonical,
                    block_ids=tuple(block.block_id for block in blocks),
                )
            )

        return SegmentationResult(
            profile_id=self.profile_id,
            profile_version=self.profile_version,
            method=self.method,
            sections=tuple(sections),
        )


class XlsxControlMatrixProfile(StructureProfile):
    """XLSX Control Matrix의 데이터 행 하나를 한 항목으로 동결한다.

    Loader가 header와 데이터 행을 한 TABLE Block으로 만들고 sheet/range locator를
    부여한다. 이 Profile은 XLSX 셀이나 OOXML을 해석하지 않고, 그 Block 경계를
    SourceReference section으로 바꾸는 역할만 한다.
    """

    profile_id = "xlsx-control-matrix"
    profile_version = "1"
    method = ExtractionMethod.DETERMINISTIC
    supported_formats = (DocumentFormat.XLSX,)

    def segment_document(self, document: CanonicalPolicyDocument) -> SegmentationResult:
        if document.detected_format is not DocumentFormat.XLSX:
            raise UnsupportedDocumentError(
                f"{self.profile_id} profile은 '{document.detected_format.value}' 문서를 "
                "처리하지 않는다"
            )

        sections: list[DocumentSection] = []
        used: dict[str, int] = {}
        for block in document.blocks:
            sheet_name, row_number = _control_matrix_location(block)
            base = f"{slugify(sheet_name) or 'sheet'}/row-{row_number}"
            seen = used.get(base, 0)
            used[base] = seen + 1
            section = base if not seen else f"{base}~{seen + 1}"
            sections.append(
                DocumentSection(
                    section=section,
                    heading_path=(sheet_name,),
                    raw_block=block.text,
                    confidence=SegmentConfidence.HIGH,
                    locator=block.locator.canonical,
                    block_ids=(block.block_id,),
                )
            )
        if not sections:
            raise UnsupportedDocumentError("Control Matrix 데이터 행이 하나도 없다")
        return SegmentationResult(
            profile_id=self.profile_id,
            profile_version=self.profile_version,
            method=self.method,
            sections=tuple(sections),
        )


def _control_matrix_location(block: CanonicalBlock) -> tuple[str, int]:
    if block.block_type is not BlockType.TABLE or block.locator.scheme != "xlsx":
        raise UnsupportedDocumentError(
            "xlsx-control-matrix profile에는 XLSX TABLE Block만 전달할 수 있다"
        )
    location = dict(block.locator.path)
    sheet = unquote(location.get("sheet", ""))
    cell_range = location.get("range", "")
    match = re.fullmatch(r"[A-Z]+([1-9][0-9]*):[A-Z]+([1-9][0-9]*)", cell_range)
    if not sheet or match is None or match.group(1) != match.group(2):
        raise UnsupportedDocumentError(
            f"Control Matrix Block locator가 올바르지 않다: {block.locator.canonical}"
        )
    return sheet, int(match.group(1))


def _anchor(heading: CanonicalBlock, order: int, used: dict[str, int]) -> str:
    anchor = "/".join(slugify(item) for item in heading.heading_path) or f"section-{order}"
    # 같은 heading 경로가 반복되면 문서 순서로 결정론적으로 구분한다.
    seen = used.get(anchor, 0)
    used[anchor] = seen + 1
    return anchor if not seen else f"{anchor}~{seen + 1}"


class LlmSegmentationProfile(StructureProfile):
    """제목 구조가 없는 임의 문서의 경로. 아직 미구현이다.

    결정론적 Profile이 실패하는 문서(제목이 없는 평문, 스캔 원문 등)에서만 쓴다.
    현재 그런 문서로 되는 것과 안 되는 것:

    - Policy Q&A: 동작한다. 원문 색인만 필요하고 항목 단위 분해가 필요 없다.
    - Rule Candidate 생성: 미동작. 항목 세그멘테이션이 선행돼야 한다.
    - Finding의 source_reference 앵커: 미동작. 항목 단위 주소가 있어야 한다.

    구현 시 반드시 충족해야 할 것:

    1. 원문 보존. ``raw_block``은 요약·재작성이 아니라 Canonical Block 그대로여야 한다.
    2. 항목별 ``confidence`` 보고. MEDIUM/LOW는 Rule Candidate 전에 사람이 확인한다.
    3. 세그멘테이션 동결. LLM은 같은 문서를 다시 처리하면 경계가 달라질 수 있으므로,
       수집 성공 시 그 document_version을 즉시 동결한다. :mod:`.ingestion` 참조.
    4. 신뢰 경계. 원문은 신뢰 경계 밖 데이터다. Prompt에 넣을 때 지시가 아닌
       데이터로 렌더링하고 길이·형식을 제약한다.
    5. 품질 측정. 결정론적 Profile 결과를 골든 기준으로 항목 경계 재현율,
       anchor 매칭률, 원문 보존 여부, 반복 실행 간 경계 안정성을 측정한다.
       이 측정 없이 임의 문서 지원을 완료로 보지 않는다.
    """

    profile_id = "llm-segmentation"
    profile_version = "0-stub"
    method = ExtractionMethod.LLM
    supported_formats = (
        DocumentFormat.MARKDOWN,
        DocumentFormat.TXT,
        DocumentFormat.HTML,
        DocumentFormat.DOCX,
        DocumentFormat.XLSX,
        DocumentFormat.PDF,
    )

    def segment_document(self, document: CanonicalPolicyDocument) -> SegmentationResult:
        raise SegmentationNotImplementedError(self._message(document.detected_format.value))

    def segment(self, raw_text: str, document_type: str) -> SegmentationResult:
        raise SegmentationNotImplementedError(self._message(document_type))

    @staticmethod
    def _message(document_type: str) -> str:
        return (
            "llm-segmentation profile은 아직 구현되지 않았다. "
            f"document_type={document_type!r}. "
            "임의 문서로 현재 가능한 것은 Policy Q&A이며, Rule Candidate 생성과 "
            "Finding의 source_reference 앵커는 세그멘테이션이 선행돼야 한다. "
            "제목 구조가 있는 문서라면 canonical-heading profile을 지정하라."
        )
