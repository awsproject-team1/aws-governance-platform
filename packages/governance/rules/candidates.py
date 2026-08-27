"""Frozen policy evidence to limited, review-only Rule Candidates.

Candidate payloads are untrusted structured output. They may propose semantic Rule
fields, but cannot choose identities, lifecycle state, approval metadata, or Source
References. Those values are bound from server-held :class:`FrozenDocument` objects.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from packages.contracts.governance import (
    ContractValidationError,
    Rule,
    SourceReference,
    SourceType,
)

from ..canonical import semantic_hash
from ..errors import GovernanceConflictError, GovernanceNotFoundError
from ..mappings.registry import SourceControlMappingRegistry
from ..sources.ingestion import FrozenDocument
from ..sources.segmentation import SegmentConfidence

PROPOSAL_FIELDS = frozenset(
    {
        "resource_type",
        "control_key",
        "evaluation_type",
        "severity",
        "requirement",
        "remediation_type",
        "limitations",
    }
)
SERVER_OWNED_FIELDS = frozenset(
    {
        "rule_id",
        "version",
        "status",
        "source_type",
        "source_reference",
        "source_references",
        "section",
        "locator",
        "content_hash",
        "approval",
        "approved_by",
        "approved_at",
        "rule_content_hash",
    }
)


@dataclass(frozen=True)
class FrozenSourceBinding:
    source_reference: SourceReference
    locator: str
    excerpt: str
    confidence: SegmentConfidence

    @classmethod
    def from_document(cls, document: FrozenDocument, section: str) -> FrozenSourceBinding:
        frozen_section = document.section_for(section)
        return cls(
            source_reference=document.reference_for(section),
            locator=frozen_section.locator or f"section:{frozen_section.section}",
            excerpt=frozen_section.raw_block,
            confidence=frozen_section.confidence,
        )

    @property
    def review_required(self) -> bool:
        return self.confidence is not SegmentConfidence.HIGH


@dataclass(frozen=True)
class RuleCandidate:
    candidate_id: str
    source_type: SourceType
    evidence: tuple[FrozenSourceBinding, ...]
    normalized_rule_fields: Mapping[str, Any]
    limitations: tuple[str, ...]
    fingerprint: str
    review_required: bool = True

    @property
    def can_be_approved(self) -> bool:
        return not self.limitations and not any(item.review_required for item in self.evidence)


@dataclass(frozen=True)
class RuleCandidateValidation:
    candidate_id: str
    valid: bool
    review_required: bool
    issues: tuple[str, ...]
    normalized_rule_fields: Mapping[str, Any] | None
    candidate: RuleCandidate | None = None


class RuleCandidateRegistry:
    """In-memory reference store; Area A may persist the same domain objects."""

    def __init__(self) -> None:
        self._candidates: dict[str, RuleCandidate] = {}
        self._fingerprints: dict[str, str] = {}
        self._approved_rules: dict[str, tuple[str, int]] = {}

    def add(self, candidate: RuleCandidate) -> None:
        if candidate.candidate_id in self._candidates:
            raise GovernanceConflictError(f"duplicate candidate_id: {candidate.candidate_id}")
        existing = self._fingerprints.get(candidate.fingerprint)
        if existing is not None:
            raise GovernanceConflictError(
                f"duplicate candidate content: {candidate.candidate_id} matches {existing}"
            )
        self._candidates[candidate.candidate_id] = candidate
        self._fingerprints[candidate.fingerprint] = candidate.candidate_id

    def get(self, candidate_id: str) -> RuleCandidate:
        try:
            return self._candidates[candidate_id]
        except KeyError as exc:
            raise GovernanceNotFoundError(f"unknown rule candidate: {candidate_id}") from exc

    def list(self) -> tuple[RuleCandidate, ...]:
        return tuple(self._candidates[key] for key in sorted(self._candidates))

    def bind_approved_rule(self, candidate_id: str, rule_identity: tuple[str, int]) -> None:
        self.get(candidate_id)
        if candidate_id in self._approved_rules:
            raise GovernanceConflictError(f"candidate already approved: {candidate_id}")
        self._approved_rules[candidate_id] = rule_identity

    def approved_rule(self, candidate_id: str) -> tuple[str, int] | None:
        self.get(candidate_id)
        return self._approved_rules.get(candidate_id)


def _limitations(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ContractValidationError("limitations must be an array")
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ContractValidationError("each limitation must be a non-empty string")
        result.append(item.strip())
    return tuple(dict.fromkeys(result))


def _build_candidate(
    candidate_id: str,
    payload: Mapping[str, Any],
    evidence: tuple[FrozenSourceBinding, ...],
    mappings: SourceControlMappingRegistry,
) -> RuleCandidate:
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ContractValidationError("candidate_id must be a non-empty server value")
    if not isinstance(payload, Mapping):
        raise ContractValidationError("candidate payload must be an object")
    protected = sorted(SERVER_OWNED_FIELDS.intersection(payload))
    if protected:
        raise ContractValidationError(
            "candidate cannot declare server-owned fields: " + ", ".join(protected)
        )
    unknown = sorted(set(payload).difference(PROPOSAL_FIELDS))
    if unknown:
        raise ContractValidationError(
            "candidate contains unsupported fields: " + ", ".join(unknown)
        )
    if not evidence:
        raise ContractValidationError("candidate requires server-bound frozen evidence")

    source_types = {mappings.source_type(item.source_reference) for item in evidence}
    if len(source_types) != 1:
        raise ContractValidationError("one Rule Candidate cannot mix GLOBAL and CUSTOMER sources")
    source_type = next(iter(source_types))
    source_references = tuple(item.source_reference for item in evidence)

    candidate_payload = {key: value for key, value in payload.items() if key != "limitations"}
    candidate_payload.update(
        {
            "rule_id": f"{source_type.value}-CANDIDATE-DRAFT-001",
            "version": 1,
            "status": "DEPRECATED",
            "source_type": source_type.value,
            "source_references": [item.to_dict() for item in source_references],
        }
    )
    rule = Rule.from_dict(candidate_payload)
    for reference in source_references:
        mappings.require(reference, rule.resource_type, rule.control_key)

    normalized = rule.to_dict()
    for field in ("rule_id", "version", "status"):
        normalized.pop(field)
    limitations = list(_limitations(payload.get("limitations")))
    for item in evidence:
        if item.review_required:
            limitations.append(
                "frozen source extraction requires human confirmation: "
                f"{item.source_reference.document_id}@"
                f"{item.source_reference.document_version}#{item.source_reference.section}"
            )
    limitations = list(dict.fromkeys(limitations))
    fingerprint = semantic_hash(
        {
            "source_references": [item.to_dict() for item in source_references],
            "rule_fields": normalized,
        }
    )
    return RuleCandidate(
        candidate_id=candidate_id,
        source_type=source_type,
        evidence=evidence,
        normalized_rule_fields=normalized,
        limitations=tuple(limitations),
        fingerprint=fingerprint,
    )


def validate_rule_candidate(
    candidate_id: str,
    payload: Mapping[str, Any],
    frozen_sources: Iterable[tuple[FrozenDocument, str]],
    mappings: SourceControlMappingRegistry,
) -> RuleCandidateValidation:
    """Bind server-held sections and validate untrusted structured output.

    ``frozen_sources`` is selected by trusted application code. A locator/hash supplied in
    ``payload`` is rejected even if it happens to match the real document.
    """
    try:
        evidence = tuple(
            FrozenSourceBinding.from_document(document, section)
            for document, section in frozen_sources
        )
        candidate = _build_candidate(candidate_id, payload, evidence, mappings)
    except (ContractValidationError, ValueError) as exc:
        return RuleCandidateValidation(
            candidate_id=candidate_id,
            valid=False,
            review_required=True,
            issues=(str(exc),),
            normalized_rule_fields=None,
        )
    return RuleCandidateValidation(
        candidate_id=candidate_id,
        valid=True,
        review_required=True,
        issues=(),
        normalized_rule_fields=candidate.normalized_rule_fields,
        candidate=candidate,
    )
