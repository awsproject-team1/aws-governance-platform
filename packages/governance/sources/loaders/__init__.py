"""Format별 Document Loader Adapter 모음."""

from __future__ import annotations

from ..canonical_document import CanonicalPolicyDocument, DocumentFormat, DocumentMetadata
from ..normalization import bytes_hash
from .base import (
    DocumentLoader,
    DocumentLoaderRegistry,
    ExtractionError,
    LoaderDependencyError,
    LoaderError,
    LoaderNotImplementedError,
    OcrRequiredError,
    UnsupportedFormatError,
)
from .docx import DocxLoader
from .html import HtmlLoader
from .markdown import MarkdownLoader
from .pdf import PdfKind, PdfTriageLoader, classify_pdf
from .xlsx import XlsxControlMatrixLoader

#: 원문 문자열만으로 Canonical Document를 만들 수 있는 형식.
TEXT_FORMATS = (DocumentFormat.MARKDOWN, DocumentFormat.TXT, DocumentFormat.HTML)


def default_loader_registry() -> DocumentLoaderRegistry:
    """MVP 기본 구성.

    MD/DOCX/HTML/PDF와 Control Matrix XLSX를 추출한다. 각 형식의 위치 정보와
    구조를 Canonical Block으로 보존한 뒤 형식에 맞는 Structure Profile이 항목을 동결한다.
    """
    return DocumentLoaderRegistry(
        [
            MarkdownLoader(),
            HtmlLoader(),
            DocxLoader(),
            XlsxControlMatrixLoader(),
            PdfTriageLoader(),
        ]
    )


def load_text_document(
    raw_text: str,
    detected_format: DocumentFormat,
    *,
    document_id: str,
    document_version: str,
) -> CanonicalPolicyDocument:
    """이미 문자열로 가진 원문을 Canonical Document로 만든다.

    업로드 경계를 거치지 않는 경로(Fixture, 이미 저장된 원문)를 위한 것이다. 업로드
    파일은 항상 :func:`packages.governance.sources.upload.validate_upload`를 먼저 지난다.
    """
    if detected_format not in TEXT_FORMATS:
        raise UnsupportedFormatError(
            f"'{detected_format.value}' 형식은 원문 문자열에서 바로 만들 수 없다. "
            "업로드 바이트와 함께 Document Loader를 거쳐야 한다."
        )
    metadata = DocumentMetadata(
        document_id=document_id,
        document_version=document_version,
        detected_format=detected_format,
        source_hash=bytes_hash(raw_text.encode("utf-8")),
    )
    loader = HtmlLoader() if detected_format is DocumentFormat.HTML else MarkdownLoader()
    return loader.load_text(raw_text, metadata)


__all__ = [
    "TEXT_FORMATS",
    "DocumentLoader",
    "DocumentLoaderRegistry",
    "DocxLoader",
    "ExtractionError",
    "HtmlLoader",
    "LoaderDependencyError",
    "LoaderError",
    "LoaderNotImplementedError",
    "MarkdownLoader",
    "OcrRequiredError",
    "PdfKind",
    "PdfTriageLoader",
    "UnsupportedFormatError",
    "XlsxControlMatrixLoader",
    "classify_pdf",
    "default_loader_registry",
    "load_text_document",
]
