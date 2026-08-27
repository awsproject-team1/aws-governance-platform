"""Allowlist-only external official evidence boundary; no network adapter is selected."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from packages.contracts.governance import (
    ContractValidationError,
    EvidenceQueryResult,
    EvidenceResultStatus,
    PolicyEvidence,
)


class ExternalEvidenceAdapter(Protocol):
    def fetch(self, source_id: str, identifier: str) -> Iterable[Mapping[str, Any]]: ...


class ExternalEvidenceService:
    def __init__(
        self,
        adapter: ExternalEvidenceAdapter,
        allowlist: Iterable[Mapping[str, str]],
    ) -> None:
        self._adapter = adapter
        self._allowlist = {item["source_id"]: item["identifier_prefix"] for item in allowlist}

    def query(self, source_id: str, identifier: str) -> EvidenceQueryResult:
        prefix = self._allowlist.get(source_id)
        if prefix is None:
            raise ContractValidationError("external evidence source is not allowed")
        if not isinstance(identifier, str) or not identifier.startswith(prefix):
            raise ContractValidationError("external evidence identifier is not allowed")
        try:
            evidence = tuple(
                PolicyEvidence.from_dict(item)
                for item in self._adapter.fetch(source_id, identifier)
            )
            for item in evidence:
                if item.source_reference.document_id != source_id:
                    raise ContractValidationError(
                        "external adapter returned evidence for a different source"
                    )
                if not item.locator.startswith(prefix):
                    raise ContractValidationError(
                        "external adapter returned an unallowed evidence locator"
                    )
        except ContractValidationError:
            raise
        except Exception:
            return EvidenceQueryResult(
                status=EvidenceResultStatus.ERROR,
                evidence=(),
                error_code="EXTERNAL_EVIDENCE_TOOL_ERROR",
            )
        if not evidence:
            return EvidenceQueryResult(status=EvidenceResultStatus.NOT_FOUND, evidence=())
        return EvidenceQueryResult(status=EvidenceResultStatus.FOUND, evidence=evidence)


class FixtureExternalEvidenceAdapter:
    def __init__(self, responses: Mapping[str, Iterable[Mapping[str, Any]]]) -> None:
        self._responses = responses

    def fetch(self, source_id: str, identifier: str):
        return self._responses.get(f"{source_id}|{identifier}", ())
