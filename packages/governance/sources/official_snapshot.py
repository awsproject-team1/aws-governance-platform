"""Frozen metadata snapshots derived from official governance references.

This module freezes a small, reviewable metadata projection instead of copying an
entire publisher page.  The projection records the observed control set and the
exact evidence used by selected Rules.  Hashes are always derived by the server;
payload-provided hashes are accepted only when they match that derivation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from packages.contracts.governance import (
    ContractValidationError,
    EvaluationType,
    Rule,
    Severity,
    SourceReference,
)

from ..canonical import semantic_hash
from .catalog import ExcludedControl, FrozenGlobalSourceSnapshot, GlobalSourceDefinition


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ContractValidationError(f"{name} must be an array")
    result = tuple(_text(item, name) for item in value)
    if len(set(result)) != len(result):
        raise ContractValidationError(f"{name} must not contain duplicates")
    return result


def _official_url(value: Any, name: str) -> str:
    value = _text(value, name)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ContractValidationError(f"{name} must be an https URL")
    return value


@dataclass(frozen=True)
class FrozenOfficialControlEvidence:
    """Minimal official metadata needed to review one selected control."""

    control_id: str
    title: str
    official_reference_url: str
    official_resource_type: str
    contract_resource_type: str
    severity: Severity
    evaluation_type: EvaluationType
    requirement: str
    required_observations: tuple[str, ...]
    content_hash: str

    @classmethod
    def create(
        cls,
        *,
        control_id: str,
        title: str,
        official_reference_url: str,
        official_resource_type: str,
        contract_resource_type: str,
        severity: Severity,
        evaluation_type: EvaluationType,
        requirement: str,
        required_observations: Sequence[str],
    ) -> FrozenOfficialControlEvidence:
        observations = _strings(required_observations, "required_observations")
        if not observations:
            raise ContractValidationError("selected control evidence requires observations")
        projection = {
            "control_id": _text(control_id, "control_id"),
            "title": _text(title, "title"),
            "official_reference_url": _official_url(
                official_reference_url, "control official_reference_url"
            ),
            "official_resource_type": _text(official_resource_type, "official_resource_type"),
            "contract_resource_type": _text(contract_resource_type, "contract_resource_type"),
            "severity": Severity(severity).value,
            "evaluation_type": EvaluationType(evaluation_type).value,
            "requirement": _text(requirement, "requirement"),
            "required_observations": list(observations),
        }
        return cls(
            control_id=projection["control_id"],
            title=projection["title"],
            official_reference_url=projection["official_reference_url"],
            official_resource_type=projection["official_resource_type"],
            contract_resource_type=projection["contract_resource_type"],
            severity=Severity(projection["severity"]),
            evaluation_type=EvaluationType(projection["evaluation_type"]),
            requirement=projection["requirement"],
            required_observations=observations,
            content_hash=semantic_hash(projection),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FrozenOfficialControlEvidence:
        try:
            severity = Severity(value.get("severity"))
            evaluation_type = EvaluationType(value.get("evaluation_type"))
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(
                "official control evidence has unknown severity or evaluation_type"
            ) from exc
        item = cls.create(
            control_id=value.get("control_id"),
            title=value.get("title"),
            official_reference_url=value.get("official_reference_url"),
            official_resource_type=value.get("official_resource_type"),
            contract_resource_type=value.get("contract_resource_type"),
            severity=severity,
            evaluation_type=evaluation_type,
            requirement=value.get("requirement"),
            required_observations=value.get("required_observations", ()),
        )
        if value.get("content_hash") != item.content_hash:
            raise ContractValidationError("official control evidence content_hash mismatch")
        return item

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "title": self.title,
            "official_reference_url": self.official_reference_url,
            "official_resource_type": self.official_resource_type,
            "contract_resource_type": self.contract_resource_type,
            "severity": self.severity.value,
            "evaluation_type": self.evaluation_type.value,
            "requirement": self.requirement,
            "required_observations": list(self.required_observations),
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class FrozenOfficialControlSet:
    """An immutable selected/excluded partition of an observed official control set."""

    snapshot_kind: str
    observed_control_ids: tuple[str, ...]
    source_snapshot: FrozenGlobalSourceSnapshot
    selected_control_evidence: tuple[FrozenOfficialControlEvidence, ...]

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        definition: GlobalSourceDefinition,
    ) -> FrozenOfficialControlSet:
        if value.get("snapshot_kind") != "official-reference-metadata":
            raise ContractValidationError("unknown official snapshot_kind")
        observed = tuple(
            sorted(_strings(value.get("observed_control_ids"), "observed_control_ids"))
        )
        if not observed:
            raise ContractValidationError("official snapshot requires observed controls")

        raw_evidence = value.get("selected_control_evidence")
        if not isinstance(raw_evidence, Sequence) or isinstance(raw_evidence, (str, bytes)):
            raise ContractValidationError("selected_control_evidence must be an array")
        evidence = tuple(FrozenOfficialControlEvidence.from_dict(item) for item in raw_evidence)
        if len({item.control_id for item in evidence}) != len(evidence):
            raise ContractValidationError("selected control evidence must not contain duplicates")

        raw_snapshot = value.get("source_snapshot")
        if not isinstance(raw_snapshot, Mapping):
            raise ContractValidationError("source_snapshot must be an object")
        raw_excluded = raw_snapshot.get("excluded_controls")
        if not isinstance(raw_excluded, Sequence) or isinstance(raw_excluded, (str, bytes)):
            raise ContractValidationError("excluded_controls must be an array")
        excluded = tuple(ExcludedControl.from_dict(item) for item in raw_excluded)
        canonical_content_hash = semantic_hash(
            {"selected_control_evidence": [item.to_dict() for item in evidence]}
        )
        if raw_snapshot.get("canonical_content_hash") != canonical_content_hash:
            raise ContractValidationError("official snapshot canonical_content_hash mismatch")

        snapshot = FrozenGlobalSourceSnapshot.create(
            source_id=raw_snapshot.get("source_id"),
            source_version=raw_snapshot.get("source_version"),
            framework_version=raw_snapshot.get("framework_version"),
            snapshot_date=raw_snapshot.get("snapshot_date"),
            collected_at=raw_snapshot.get("collected_at"),
            official_reference_url=raw_snapshot.get("official_reference_url"),
            canonical_content_hash=canonical_content_hash,
            selected_control_ids=raw_snapshot.get("selected_control_ids", ()),
            excluded_controls=excluded,
            mapping_version=raw_snapshot.get("mapping_version"),
        )
        if raw_snapshot.get("control_set_hash") != snapshot.control_set_hash:
            raise ContractValidationError("official snapshot control_set_hash mismatch")
        if snapshot.source_id != definition.source_id:
            raise ContractValidationError("official snapshot source_id differs from catalog")
        if snapshot.framework_version != definition.framework_version:
            raise ContractValidationError(
                "official snapshot framework_version differs from catalog"
            )
        if snapshot.official_reference_url != definition.official_reference_url:
            raise ContractValidationError("official snapshot reference differs from catalog")

        selected = set(snapshot.selected_control_ids)
        excluded_ids = {item.control_id for item in snapshot.excluded_controls}
        if selected | excluded_ids != set(observed):
            raise ContractValidationError(
                "selected and excluded controls must exactly partition observed controls"
            )
        if {item.control_id for item in evidence} != selected:
            raise ContractValidationError(
                "selected_control_evidence must exactly match selected controls"
            )
        return cls(
            snapshot_kind="official-reference-metadata",
            observed_control_ids=observed,
            source_snapshot=snapshot,
            selected_control_evidence=evidence,
        )

    def evidence_for(self, control_id: str) -> FrozenOfficialControlEvidence:
        for item in self.selected_control_evidence:
            if item.control_id == control_id:
                return item
        raise ContractValidationError(f"control is not selected in snapshot: {control_id}")

    def source_reference_for(self, control_id: str) -> SourceReference:
        evidence = self.evidence_for(control_id)
        return SourceReference(
            document_id=self.source_snapshot.source_id,
            document_version=self.source_snapshot.source_version,
            section=evidence.control_id,
            content_hash=evidence.content_hash,
        )


@dataclass(frozen=True)
class RuleSourceRevalidation:
    rule_id: str
    rule_version: int
    source_reference_matches: bool
    semantic_fields_match: bool
    requires_new_rule_version_and_human_approval: bool
    reasons: tuple[str, ...]
    current_source_reference: SourceReference


def revalidate_rule_against_official_snapshot(
    rule: Rule,
    control_set: FrozenOfficialControlSet,
    control_id: str,
) -> RuleSourceRevalidation:
    """Compare without mutating, approving, versioning, or activating the Rule."""
    evidence = control_set.evidence_for(control_id)
    current_reference = control_set.source_reference_for(control_id)
    reference_matches = current_reference in rule.source_references
    semantic_fields_match = (
        rule.resource_type == evidence.contract_resource_type
        and rule.severity is evidence.severity
        and rule.evaluation_type is evidence.evaluation_type
        and rule.requirement == evidence.requirement
    )
    reasons: list[str] = []
    if not reference_matches:
        reasons.append("approved SourceReference is not the frozen official snapshot reference")
    if not semantic_fields_match:
        reasons.append("approved Rule semantic fields differ from frozen official evidence")
    requires_reapproval = not reference_matches or not semantic_fields_match
    return RuleSourceRevalidation(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        source_reference_matches=reference_matches,
        semantic_fields_match=semantic_fields_match,
        requires_new_rule_version_and_human_approval=requires_reapproval,
        reasons=tuple(reasons),
        current_source_reference=current_reference,
    )
