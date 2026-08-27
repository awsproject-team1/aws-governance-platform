"""Policy Knowledge read boundary with structured, validated results."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from packages.contracts.governance import (
    ContractValidationError,
    EvidenceQueryResult,
    EvidenceResultStatus,
    PolicyEvidence,
)
from packages.governance.mappings.registry import SourceControlMappingRegistry
from packages.governance.sources.index import FrozenDocumentIndex


class PolicyKnowledgeAdapter(Protocol):
    def search(
        self, query: str, allowed_source_ids: tuple[str, ...]
    ) -> Iterable[Mapping[str, Any]]: ...


class PolicyKnowledgeService:
    """Adapter 결과를 등록된 근거로만 좁히는 읽기 경계.

    Reference가 유효한 경로는 두 가지다.

    - Control에 Mapping된 Source Reference: Rule 근거로 이미 등록된 항목.
    - 동결된 업로드 문서의 항목: Q&A 대상이지만 아직 Control에 Mapping되지 않은 항목.

    두 번째 경로가 없으면 사용자가 올린 사내 규정은 Rule로 승격되기 전까지 Q&A에
    쓸 수 없다. 그렇다고 검증 없이 통과시키면 Adapter가 만들어낸 section/hash가
    그대로 Evidence가 된다. 그래서 동결 Index와 정확히 대조한다.
    """

    def __init__(
        self,
        adapter: PolicyKnowledgeAdapter,
        mappings: SourceControlMappingRegistry,
        documents: FrozenDocumentIndex | None = None,
    ) -> None:
        self._adapter = adapter
        self._mappings = mappings
        self._documents = documents

    def _is_registered(self, reference) -> bool:
        if self._mappings.allows_reference(reference):
            return True
        return self._documents is not None and self._documents.verifies(reference)

    def query(self, query: str, allowed_source_ids: Iterable[str]) -> EvidenceQueryResult:
        if not isinstance(query, str) or not query.strip():
            raise ContractValidationError("policy knowledge query must be non-empty")
        allowed = tuple(sorted(set(allowed_source_ids)))
        if not allowed:
            raise ContractValidationError("at least one allowed source_id is required")
        try:
            raw_items = tuple(self._adapter.search(query, allowed))
            evidence = tuple(PolicyEvidence.from_dict(item) for item in raw_items)
            for item in evidence:
                if item.source_reference.document_id not in allowed:
                    raise ContractValidationError(
                        "adapter returned evidence outside allowed sources"
                    )
                if not self._is_registered(item.source_reference):
                    raise ContractValidationError(
                        "adapter returned an unregistered source reference"
                    )
        except ContractValidationError:
            raise
        except Exception:
            return EvidenceQueryResult(
                status=EvidenceResultStatus.ERROR,
                evidence=(),
                error_code="POLICY_KNOWLEDGE_TOOL_ERROR",
            )
        if not evidence:
            return EvidenceQueryResult(status=EvidenceResultStatus.NOT_FOUND, evidence=())
        return EvidenceQueryResult(status=EvidenceResultStatus.FOUND, evidence=evidence)


class FrozenDocumentKnowledgeAdapter:
    """업로드된 사내 규정을 대상으로 하는 Adapter.

    Vendor Retrieval을 붙이기 전의 결정론적 기본 구현이다. 동결된 항목만 대상으로
    하므로 결과의 section/content_hash는 항상 원문과 일치한다.
    """

    def __init__(self, index: FrozenDocumentIndex, limit: int = 5) -> None:
        self._index = index
        self._limit = limit

    def search(self, query: str, allowed_source_ids: tuple[str, ...]):
        return self._index.search(query, allowed_source_ids, limit=self._limit)


class FixturePolicyKnowledgeAdapter:
    def __init__(self, evidence: Iterable[Mapping[str, Any]]) -> None:
        self._evidence = tuple(evidence)

    def search(self, query: str, allowed_source_ids: tuple[str, ...]):
        tokens = {token.casefold() for token in query.split() if token.strip()}
        for item in self._evidence:
            source_id = item.get("source_reference", {}).get("document_id")
            text = str(item.get("excerpt", "")).casefold()
            if source_id in allowed_source_ids and any(token in text for token in tokens):
                yield item
