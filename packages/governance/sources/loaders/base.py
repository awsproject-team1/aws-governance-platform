"""Document Loader Port.

Loader는 "이 형식의 원문을 Canonical Block으로 바꾸는 것"만 한다. 구체 라이브러리
이름은 Contract가 아니라 Adapter 구현 안에서만 고른다. Loader가 하지 않는 것:

- 실제 파일 형식 판별(upload.py의 책임)
- anchor 생성, content_hash 계산, 동결 비교(segmentation/ingestion의 책임)
- 의미 판정, Rule/Severity 결정

미구현 형식은 빈 문서를 돌려주지 않고 실패한다. 빈 결과를 성공으로 위장하면
"업로드는 됐는데 Rule이 안 나온다"가 되어 어디서 막혔는지 드러나지 않는다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from ...errors import GovernanceValidationError
from ..canonical_document import (
    CanonicalPolicyDocument,
    DocumentFormat,
    DocumentMetadata,
)


class LoaderError(GovernanceValidationError):
    """Loader 단계 실패의 공통 상위 타입."""


class UnsupportedFormatError(LoaderError):
    """등록된 Loader 중 이 형식을 처리하는 Loader가 없다."""


class LoaderNotImplementedError(LoaderError):
    """형식은 알지만 Loader가 아직 없다. 미구현을 성공으로 위장하지 않는다."""


class ExtractionError(LoaderError):
    """원문을 열었지만 구조를 꺼낼 수 없다."""


class OcrRequiredError(LoaderError):
    """텍스트 계층이 없어 OCR Adapter와 Review 흐름이 필요하다.

    스캔 PDF를 빈 문서로 처리하면 "정책이 하나도 없는 문서"로 조용히 통과한다.
    """


class DocumentLoader(ABC):
    parser_profile: str
    parser_version: str
    supported_formats: tuple[DocumentFormat, ...] = ()

    def supports(self, detected_format: DocumentFormat) -> bool:
        return detected_format in self.supported_formats

    @abstractmethod
    def load(self, content: bytes, metadata: DocumentMetadata) -> CanonicalPolicyDocument:
        raise NotImplementedError


class DocumentLoaderRegistry:
    """형식 -> Loader 선택. 같은 형식에 두 Loader를 등록하지 않는다."""

    def __init__(self, loaders: Iterable[DocumentLoader] = ()) -> None:
        self._loaders: dict[DocumentFormat, DocumentLoader] = {}
        for loader in loaders:
            self.register(loader)

    def register(self, loader: DocumentLoader) -> None:
        if not loader.supported_formats:
            raise GovernanceValidationError(
                f"{type(loader).__name__}이 지원 형식을 선언하지 않았다"
            )
        for item in loader.supported_formats:
            if item in self._loaders:
                raise GovernanceValidationError(f"'{item.value}' 형식에 Loader가 이미 있다")
            self._loaders[item] = loader

    def for_format(self, detected_format: DocumentFormat) -> DocumentLoader:
        loader = self._loaders.get(detected_format)
        if loader is None:
            raise UnsupportedFormatError(
                f"'{detected_format.value}' 형식을 처리할 Document Loader가 없다"
            )
        return loader

    def load(self, content: bytes, metadata: DocumentMetadata) -> CanonicalPolicyDocument:
        document = self.for_format(metadata.detected_format).load(content, metadata)
        if not document.blocks:
            raise ExtractionError(
                f"'{metadata.document_id}'에서 Block을 하나도 얻지 못했다. "
                "빈 추출 결과를 성공으로 취급하지 않는다."
            )
        return document
