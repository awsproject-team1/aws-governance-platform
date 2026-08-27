"""형식 비종속 Canonical Policy Document.

업로드된 파일은 형식마다 구조가 다르지만 그 구조를 곧바로 문자열로 평탄화하면
DOCX 표, XLSX 셀, PDF 페이지, HTML DOM 위치가 추출 시점에 사라진다. 그 정보가
사라지면 Evidence가 "문서 어디"를 가리키는지 되돌릴 수 없다.

그래서 경계를 다음처럼 둔다::

    Uploaded File
      -> 보안 검사 및 실제 형식 확인      (upload.py)
      -> Format별 Document Loader          (loaders/)
      -> Canonical Policy Document         (이 모듈)
      -> 결정론적 Segmentation             (segmentation.py)
      -> Frozen Document + SourceReference (ingestion.py)

Loader는 형식 지식을 전부 가지되 anchor/해시/동결 규칙은 갖지 않는다. 이 모듈의
Block이 그 두 세계가 만나는 유일한 자료구조다.

``SourceReference.section`` Contract는 그대로 둔다. Block의 ``locator``는 안정적인
canonical 문자열로만 노출하며, 구조화된 locator metadata를 Contract에 올릴지는
docs/CONTRACTS.md의 Contract Review 대상이다.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from ..errors import GovernanceValidationError
from .normalization import content_hash, normalize_for_hash


class DocumentFormat(str, Enum):
    MARKDOWN = "md"
    TXT = "txt"
    HTML = "html"
    DOCX = "docx"
    XLSX = "xlsx"
    PDF = "pdf"


#: 같은 형식을 가리키는 다른 표기. 새 형식을 여기에서 만들지 않는다.
FORMAT_ALIASES: dict[str, DocumentFormat] = {
    "markdown": DocumentFormat.MARKDOWN,
    "htm": DocumentFormat.HTML,
    "text": DocumentFormat.TXT,
    "plain": DocumentFormat.TXT,
}


def resolve_format(document_type: str) -> DocumentFormat | None:
    """문서 타입 문자열을 형식으로 바꾼다. 모르면 None이며 추측하지 않는다."""
    if not isinstance(document_type, str):
        return None
    key = document_type.strip().casefold().lstrip(".")
    if key in FORMAT_ALIASES:
        return FORMAT_ALIASES[key]
    try:
        return DocumentFormat(key)
    except ValueError:
        return None


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CELL = "cell"
    CODE = "code"
    QUOTE = "quote"


#: locator 값에 쓸 수 없는 문자. canonical 문자열의 구분자와 충돌한다.
_LOCATOR_FORBIDDEN = ("=", "/", "\n", "\r")


@dataclass(frozen=True)
class SourceLocator:
    """Block이 원문 어디에서 왔는지. 형식별 의미를 값이 아니라 key로 구분한다.

    형식별 보존 대상::

        Markdown  md:line=12
        HTML      html:dom=body>div[2]>h2[1]
        DOCX      docx:body=7 / docx:body=9/row=2/cell=1
        PDF       pdf:page=3/block=2
        XLSX      xlsx:sheet=Controls/range=A3:D3

    ``canonical``은 Evidence의 ``locator``로 그대로 쓸 수 있는 안정적 문자열이다.
    """

    scheme: str
    path: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.scheme or any(char in self.scheme for char in _LOCATOR_FORBIDDEN):
            raise GovernanceValidationError(f"locator scheme이 올바르지 않다: {self.scheme!r}")
        if not self.path:
            raise GovernanceValidationError("locator는 최소 한 개의 위치 정보를 가져야 한다")
        for key, value in self.path:
            if not key or not value:
                raise GovernanceValidationError("locator의 key와 value는 비어 있을 수 없다")
            if any(char in key for char in _LOCATOR_FORBIDDEN):
                raise GovernanceValidationError(f"locator key에 금지 문자가 있다: {key!r}")
            if any(char in value for char in _LOCATOR_FORBIDDEN):
                raise GovernanceValidationError(f"locator value에 금지 문자가 있다: {value!r}")

    @classmethod
    def of(cls, scheme: str, **path: object) -> SourceLocator:
        return cls(scheme=scheme, path=tuple((key, str(value)) for key, value in path.items()))

    def child(self, **path: object) -> SourceLocator:
        extra = tuple((key, str(value)) for key, value in path.items())
        return SourceLocator(scheme=self.scheme, path=self.path + extra)

    @property
    def canonical(self) -> str:
        return f"{self.scheme}:" + "/".join(f"{key}={value}" for key, value in self.path)

    def __str__(self) -> str:
        return self.canonical


@dataclass(frozen=True)
class CanonicalBlock:
    """원문 한 덩어리. 형식에 관계없이 같은 필드를 갖는다."""

    block_id: str
    block_type: BlockType
    text: str
    locator: SourceLocator
    heading_path: tuple[str, ...] = ()
    heading_level: int | None = None

    def __post_init__(self) -> None:
        if not self.block_id:
            raise GovernanceValidationError("block_id는 비어 있을 수 없다")
        if not self.text:
            raise GovernanceValidationError(f"block {self.block_id}의 text가 비어 있다")
        if self.block_type is BlockType.HEADING and self.heading_level is None:
            raise GovernanceValidationError("heading block은 heading_level을 가져야 한다")

    @property
    def content_hash(self) -> str:
        return content_hash(self.text)


def render_blocks(blocks: Sequence[CanonicalBlock]) -> str:
    """Block 묶음을 결정론적 원문 조각으로 되돌린다.

    ``content_hash``의 입력이므로 규칙은 형식과 무관하게 하나여야 한다. Block 사이는
    빈 줄 하나로 구분하고, Block 내부 줄바꿈(목록 이어짐, 표의 행)은 그대로 둔다.
    """
    return "\n\n".join(block.text for block in blocks)


@dataclass(frozen=True)
class CanonicalPolicyDocument:
    """한 업로드본의 형식 비종속 표현."""

    document_id: str
    document_version: str
    detected_format: DocumentFormat
    source_hash: str
    parser_profile: str
    parser_version: str
    blocks: tuple[CanonicalBlock, ...]
    extraction_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        ids = [block.block_id for block in self.blocks]
        if len(set(ids)) != len(ids):
            raise GovernanceValidationError("block_id가 문서 안에서 중복됐다")

    @property
    def parser_identity(self) -> str:
        return f"{self.parser_profile}@{self.parser_version}"

    def headings(self) -> tuple[CanonicalBlock, ...]:
        return tuple(block for block in self.blocks if block.block_type is BlockType.HEADING)

    def with_warnings(self, extra: Iterable[str]) -> CanonicalPolicyDocument:
        merged = list(self.extraction_warnings)
        for item in extra:
            if item and item not in merged:
                merged.append(item)
        return CanonicalPolicyDocument(
            document_id=self.document_id,
            document_version=self.document_version,
            detected_format=self.detected_format,
            source_hash=self.source_hash,
            parser_profile=self.parser_profile,
            parser_version=self.parser_version,
            blocks=self.blocks,
            extraction_warnings=tuple(merged),
        )


@dataclass(frozen=True)
class DocumentMetadata:
    """Loader에 넘기는 문서 정체성. Loader는 이 값을 스스로 만들지 않는다."""

    document_id: str
    document_version: str
    detected_format: DocumentFormat
    source_hash: str


class CanonicalDocumentBuilder:
    """Loader가 Block을 쌓는 유일한 통로.

    ``block_id``와 ``heading_path``를 Loader마다 다시 구현하면 형식별로 규칙이 갈라진다.
    그래서 heading 계층 추적과 텍스트 정규화를 여기에서만 수행한다.
    """

    def __init__(self, metadata: DocumentMetadata, *, parser_profile: str, parser_version: str):
        self._metadata = metadata
        self._parser_profile = parser_profile
        self._parser_version = parser_version
        self._blocks: list[CanonicalBlock] = []
        self._warnings: list[str] = []
        self._path: list[tuple[int, str]] = []

    def heading(self, level: int, text: str, locator: SourceLocator) -> CanonicalBlock | None:
        if level < 1:
            raise GovernanceValidationError("heading level은 1 이상이어야 한다")
        normalized = normalize_for_hash(text).strip()
        if not normalized:
            self.warn(f"빈 heading을 건너뛰었다: {locator.canonical}")
            return None
        while self._path and self._path[-1][0] >= level:
            self._path.pop()
        self._path.append((level, normalized))
        return self._append(BlockType.HEADING, normalized, locator, heading_level=level)

    def block(
        self, block_type: BlockType, text: str, locator: SourceLocator
    ) -> CanonicalBlock | None:
        if block_type is BlockType.HEADING:
            raise GovernanceValidationError("heading은 heading()으로 추가한다")
        normalized = normalize_for_hash(text)
        if not normalized.strip():
            return None
        return self._append(block_type, normalized, locator)

    def warn(self, message: str) -> None:
        if message not in self._warnings:
            self._warnings.append(message)

    def _append(
        self,
        block_type: BlockType,
        text: str,
        locator: SourceLocator,
        *,
        heading_level: int | None = None,
    ) -> CanonicalBlock:
        block = CanonicalBlock(
            block_id=f"b{len(self._blocks) + 1:04d}",
            block_type=block_type,
            text=text,
            locator=locator,
            heading_path=tuple(item[1] for item in self._path),
            heading_level=heading_level,
        )
        self._blocks.append(block)
        return block

    def build(self) -> CanonicalPolicyDocument:
        return CanonicalPolicyDocument(
            document_id=self._metadata.document_id,
            document_version=self._metadata.document_version,
            detected_format=self._metadata.detected_format,
            source_hash=self._metadata.source_hash,
            parser_profile=self._parser_profile,
            parser_version=self._parser_version,
            blocks=tuple(self._blocks),
            extraction_warnings=tuple(self._warnings),
        )
