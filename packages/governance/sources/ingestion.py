"""업로드된 임의 정책 문서를 동결된 Source Reference 집합으로 만든다.

동결(freeze)이 이 모듈의 존재 이유다. 세그멘테이션 경계가 재수집 때마다 달라지면
``section`` anchor와 ``content_hash``가 바뀌고, 과거 Finding이 참조한 원문 조각을
더 이상 찾을 수 없다. 그러면 "과거 Assessment를 당시 기준으로 재현한다"는 보증이
깨진다. LLM 세그멘테이션은 본질적으로 비결정론적이므로 이 위험이 실재한다.

규칙:

1. 수집이 성공하면 해당 ``document_version``을 즉시 동결한다.
2. 동결된 version은 재수집해도 기존 항목 집합을 덮어쓰지 않는다. 해시를 비교해
   동일함을 확인하고, 다르면 실패한다.
3. 원문이 개정되면 기존 version을 고치지 않고 새 version을 발급한다.
4. 과거 Finding은 계속 이전 version의 동결된 항목을 참조한다.

전체 경로::

    UploadedFile -> validate_upload -> Document Loader -> CanonicalPolicyDocument
                 -> Structure Profile -> FrozenDocument -> SourceReference
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.contracts.governance import PolicySource, SourceReference, SourceType

from ..canonical import semantic_hash
from ..errors import GovernanceConflictError, GovernanceValidationError
from .canonical_document import (
    CanonicalPolicyDocument,
    DocumentFormat,
    DocumentMetadata,
    resolve_format,
)
from .loaders import DocumentLoaderRegistry, default_loader_registry, load_text_document
from .segmentation import (
    DocumentSection,
    ExtractionMethod,
    SegmentationResult,
    StructureProfile,
)
from .upload import MalwareScanner, UploadedFile, ValidatedUpload, validate_upload


@dataclass(frozen=True)
class DocumentIdentity:
    """업로드본에 부여하는 정체성. 사용자가 정한 파일명이 아니라 관리자가 정한다."""

    document_id: str
    document_version: str
    source_type: SourceType


@dataclass(frozen=True)
class PolicyDocument:
    """이미 문자열로 가진 원문. 저장 위치와 업로드 API는 이 계층의 관심사가 아니다."""

    document_id: str
    document_version: str
    document_type: str
    source_type: SourceType
    raw_text: str

    @property
    def identity(self) -> DocumentIdentity:
        return DocumentIdentity(
            document_id=self.document_id,
            document_version=self.document_version,
            source_type=self.source_type,
        )


@dataclass(frozen=True)
class FrozenDocument:
    """한 document_version의 동결된 항목 집합."""

    document_id: str
    document_version: str
    document_type: str
    source_type: SourceType
    detected_format: DocumentFormat
    source_hash: str
    parser_profile: str
    parser_version: str
    profile_id: str
    profile_version: str
    method: ExtractionMethod
    sections: tuple[DocumentSection, ...]
    snapshot_hash: str
    extraction_warnings: tuple[str, ...] = ()

    @property
    def policy_source(self) -> PolicySource:
        return PolicySource(
            source_id=self.document_id,
            source_type=self.source_type,
            source_version=self.document_version,
        )

    def source_references(self) -> tuple[SourceReference, ...]:
        """Mapping/Rule이 참조할 수 있는 검증된 Source Reference."""
        return tuple(
            SourceReference(
                document_id=self.document_id,
                document_version=self.document_version,
                section=item.section,
                content_hash=item.content_hash,
            )
            for item in self.sections
        )

    def section_for(self, section: str) -> DocumentSection:
        for item in self.sections:
            if item.section == section:
                return item
        raise GovernanceValidationError(
            f"'{self.document_id}@{self.document_version}'에 section이 없다: {section}"
        )

    def reference_for(self, section: str) -> SourceReference:
        item = self.section_for(section)
        return SourceReference(
            document_id=self.document_id,
            document_version=self.document_version,
            section=item.section,
            content_hash=item.content_hash,
        )

    def sections_requiring_review(self) -> tuple[DocumentSection, ...]:
        """Rule Candidate로 넘기기 전에 사람이 확인해야 하는 항목."""
        return tuple(item for item in self.sections if item.review_required)


def _snapshot_hash(document: CanonicalPolicyDocument, result: SegmentationResult) -> str:
    """동결 비교의 기준값.

    Parser/Profile 정체성과 항목 경계·내용만 해시한다. 원문 전체 바이트(``source_hash``)를
    넣지 않는 이유는, 판정에 영향을 주지 않는 줄바꿈이나 문서 말미의 공백 변화까지
    동결 위반으로 만들지 않기 위해서다. 반대로 Parser version은 반드시 넣는다. Parser가
    바뀌어 Block 경계가 달라졌는데 같은 version으로 통과하면 과거 Finding의 근거가
    조용히 달라진다.
    """
    return semantic_hash(
        {
            "document_id": document.document_id,
            "document_version": document.document_version,
            "detected_format": document.detected_format.value,
            "parser_profile": document.parser_profile,
            "parser_version": document.parser_version,
            "profile_id": result.profile_id,
            "profile_version": result.profile_version,
            "sections": [
                {"section": item.section, "content_hash": item.content_hash}
                for item in result.sections
            ],
        }
    )


def ingest_canonical(
    document: CanonicalPolicyDocument,
    source_type: SourceType,
    profile: StructureProfile,
    *,
    document_type: str | None = None,
) -> FrozenDocument:
    """Canonical Document를 항목으로 쪼개고 그 결과를 동결한다."""
    result = profile.segment_document(document)
    if not result.sections:
        raise GovernanceValidationError(
            f"'{document.document_id}'에서 항목을 하나도 얻지 못했다. "
            "빈 결과를 성공으로 취급하지 않는다."
        )
    return FrozenDocument(
        document_id=document.document_id,
        document_version=document.document_version,
        document_type=document_type or document.detected_format.value,
        source_type=source_type,
        detected_format=document.detected_format,
        source_hash=document.source_hash,
        parser_profile=document.parser_profile,
        parser_version=document.parser_version,
        profile_id=result.profile_id,
        profile_version=result.profile_version,
        method=result.method,
        sections=result.sections,
        snapshot_hash=_snapshot_hash(document, result),
        extraction_warnings=document.extraction_warnings,
    )


def load_upload(
    upload: UploadedFile,
    identity: DocumentIdentity,
    *,
    loaders: DocumentLoaderRegistry | None = None,
    scanner: MalwareScanner | None = None,
) -> tuple[CanonicalPolicyDocument, ValidatedUpload]:
    """업로드 파일을 보안 검사 후 Canonical Document로 만든다.

    검사와 추출을 한 함수에 묶는 이유는, 검사되지 않은 바이트가 Parser에 도달하는
    경로를 코드에 남기지 않기 위해서다.
    """
    validated = validate_upload(upload, scanner=scanner)
    metadata = DocumentMetadata(
        document_id=identity.document_id,
        document_version=identity.document_version,
        detected_format=validated.detected_format,
        source_hash=validated.source_hash,
    )
    registry = loaders if loaders is not None else default_loader_registry()
    document = registry.load(upload.content, metadata)
    return document.with_warnings(validated.warnings), validated


def ingest_upload(
    upload: UploadedFile,
    identity: DocumentIdentity,
    profile: StructureProfile,
    *,
    loaders: DocumentLoaderRegistry | None = None,
    scanner: MalwareScanner | None = None,
) -> FrozenDocument:
    """업로드 파일 하나를 동결된 항목 집합까지 처리한다."""
    document, _ = load_upload(upload, identity, loaders=loaders, scanner=scanner)
    return ingest_canonical(document, identity.source_type, profile)


def load_policy_document(document: PolicyDocument) -> CanonicalPolicyDocument:
    detected = resolve_format(document.document_type)
    if detected is None:
        raise GovernanceValidationError(f"알 수 없는 document_type이다: {document.document_type!r}")
    return load_text_document(
        document.raw_text,
        detected,
        document_id=document.document_id,
        document_version=document.document_version,
    )


def ingest_document(document: PolicyDocument, profile: StructureProfile) -> FrozenDocument:
    """문자열 원문 경로. 업로드 파일은 :func:`ingest_upload`을 쓴다."""
    return ingest_canonical(
        load_policy_document(document),
        document.source_type,
        profile,
        document_type=document.document_type,
    )


def _require_same_identity(frozen: FrozenDocument, document_id: str, version: str) -> None:
    if (document_id, version) != (frozen.document_id, frozen.document_version):
        raise GovernanceValidationError("재수집 대상의 document identity가 동결된 문서와 다르다")


def _require_same_snapshot(frozen: FrozenDocument, candidate: FrozenDocument) -> FrozenDocument:
    if candidate.snapshot_hash != frozen.snapshot_hash:
        raise GovernanceConflictError(
            f"'{frozen.document_id}@{frozen.document_version}'은 이미 동결됐고 "
            "재수집 결과가 동결된 항목 집합과 다르다. 같은 version을 덮어쓰지 말고 "
            "새 document_version을 발급하라."
        )
    return frozen


def reingest_document(
    frozen: FrozenDocument, document: PolicyDocument, profile: StructureProfile
) -> FrozenDocument:
    """이미 동결된 version을 재수집한다. 결과가 다르면 덮어쓰지 않고 실패한다.

    원문이 개정됐다면 새 ``document_version``을 발급해야 한다. 같은 version의 내용을
    바꾸면 그 version을 참조하는 과거 Finding의 근거가 조용히 달라진다.
    """
    _require_same_identity(frozen, document.document_id, document.document_version)
    return _require_same_snapshot(frozen, ingest_document(document, profile))


def reingest_upload(
    frozen: FrozenDocument,
    upload: UploadedFile,
    identity: DocumentIdentity,
    profile: StructureProfile,
    *,
    loaders: DocumentLoaderRegistry | None = None,
    scanner: MalwareScanner | None = None,
) -> FrozenDocument:
    """업로드 경로의 재수집. 같은 version에 다른 내용을 올리면 실패한다."""
    _require_same_identity(frozen, identity.document_id, identity.document_version)
    candidate = ingest_upload(upload, identity, profile, loaders=loaders, scanner=scanner)
    return _require_same_snapshot(frozen, candidate)
