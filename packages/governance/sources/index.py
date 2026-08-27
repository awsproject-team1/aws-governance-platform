"""동결된 문서의 Knowledge Index.

Policy Q&A가 "업로드한 임의 문서"를 실제로 답할 수 있으려면 다음 연결이 필요하다::

    FrozenDocument.sections
      -> Knowledge Index
      -> document_id/version 범위 검색
      -> PolicyEvidence
      -> 원문 locator와 함께 답변

이 Index는 동결된 항목만 담는다. 그래서 검색 결과의 ``content_hash``는 항상 동결
시점의 원문과 일치하며, Adapter가 만들어낸 근거를 :meth:`verifies`로 걸러낼 수 있다.

검색은 결정론적이다. 같은 질의는 항상 같은 순서를 낸다. Vendor Retrieval을 붙일 때도
"동결된 항목만, 허용된 Source만"이라는 이 경계는 그대로 유지한다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from packages.contracts.governance import SourceReference

from ..errors import GovernanceConflictError
from .ingestion import FrozenDocument
from .segmentation import DocumentSection

#: excerpt로 실어 보낼 최대 길이. 원문 전체를 Prompt에 넣지 않는다.
DEFAULT_EXCERPT_CHARS = 400
DEFAULT_LIMIT = 5

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> tuple[str, ...]:
    """한글/영문 공통 토큰. 형태소 분석을 가정하지 않고 부분 일치로 쓴다."""
    return tuple(token.casefold() for token in _TOKEN.findall(text) if len(token) > 1)


class FrozenDocumentIndex:
    def __init__(self, documents: Iterable[FrozenDocument] = ()) -> None:
        self._documents: dict[tuple[str, str], FrozenDocument] = {}
        for document in documents:
            self.add(document)

    def add(self, document: FrozenDocument) -> None:
        key = (document.document_id, document.document_version)
        existing = self._documents.get(key)
        if existing is not None and existing.snapshot_hash != document.snapshot_hash:
            raise GovernanceConflictError(
                f"'{key[0]}@{key[1]}'은 이미 다른 내용으로 동결됐다. "
                "새 document_version을 발급하라."
            )
        self._documents[key] = document

    def documents(self) -> tuple[FrozenDocument, ...]:
        return tuple(self._documents[key] for key in sorted(self._documents))

    def versions_of(self, document_id: str) -> tuple[str, ...]:
        return tuple(sorted(key[1] for key in self._documents if key[0] == document_id))

    def verifies(self, reference: SourceReference) -> bool:
        """이 Reference가 동결된 항목과 정확히 일치하는가.

        Adapter나 LLM이 만들어낸 section/content_hash를 걸러내는 지점이다.
        """
        document = self._documents.get((reference.document_id, reference.document_version))
        if document is None:
            return False
        return any(
            item.section == reference.section and item.content_hash == reference.content_hash
            for item in document.sections
        )

    def search(
        self,
        query: str,
        allowed_source_ids: Iterable[str],
        *,
        limit: int = DEFAULT_LIMIT,
        excerpt_chars: int = DEFAULT_EXCERPT_CHARS,
    ) -> tuple[Mapping[str, Any], ...]:
        """허용된 Source의 동결 항목만 검색해 PolicyEvidence 형태로 돌려준다."""
        allowed = {item for item in allowed_source_ids}
        tokens = tokenize(query)
        if not tokens:
            return ()

        scored: list[tuple[int, str, str, FrozenDocument, DocumentSection]] = []
        for document in self.documents():
            if document.document_id not in allowed:
                continue
            for section in document.sections:
                score = _score(section, tokens)
                if score:
                    scored.append(
                        (-score, document.document_id, section.section, document, section)
                    )

        scored.sort(key=lambda item: item[:3])
        return tuple(
            _evidence(document, section, tokens, excerpt_chars)
            for _, _, _, document, section in scored[: max(limit, 0)]
        )


def _score(section: DocumentSection, tokens: tuple[str, ...]) -> int:
    body = section.raw_block.casefold()
    heading = " ".join(section.heading_path).casefold()
    score = 0
    for token in set(tokens):
        if token in heading:
            score += 2
        elif token in body:
            score += 1
    return score


def _excerpt(section: DocumentSection, tokens: tuple[str, ...], limit: int) -> str:
    """원문 한 줄을 그대로 잘라 쓴다. 요약하거나 문장을 만들지 않는다."""
    lines = [line for line in section.raw_block.split("\n") if line.strip()]
    for line in lines:
        lowered = line.casefold()
        if any(token in lowered for token in tokens):
            return line[:limit]
    return lines[0][:limit] if lines else section.section


def _evidence(
    document: FrozenDocument,
    section: DocumentSection,
    tokens: tuple[str, ...],
    excerpt_chars: int,
) -> Mapping[str, Any]:
    return {
        "evidence_id": (f"{document.document_id}@{document.document_version}#{section.section}"),
        "source_reference": {
            "document_id": document.document_id,
            "document_version": document.document_version,
            "section": section.section,
            "content_hash": section.content_hash,
        },
        "locator": section.locator or f"section:{section.section}",
        "excerpt": _excerpt(section, tokens, excerpt_chars),
    }
