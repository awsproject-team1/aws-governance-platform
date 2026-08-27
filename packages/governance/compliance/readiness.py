"""Mapping and evidence readiness without producing a compliance score."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from packages.contracts.governance import ContractValidationError, RulePin


class EvidenceReadinessStatus(str, Enum):
    AUTOMATED_EVIDENCE = "AUTOMATED_EVIDENCE"
    PARTIAL_EVIDENCE = "PARTIAL_EVIDENCE"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


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


@dataclass(frozen=True)
class ComplianceItemMapping:
    item_id: str
    item_title: str
    applicability_scope: str
    project_control_keys: tuple[str, ...]
    rule_pins: tuple[RulePin, ...]
    automated_evidence_ids: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    finding_ids: tuple[str, ...]
    remediation_ids: tuple[str, ...]
    evidence_status: EvidenceReadinessStatus

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ComplianceItemMapping:
        raw_pins = value.get("rule_pins", ())
        if not isinstance(raw_pins, Sequence) or isinstance(raw_pins, (str, bytes)):
            raise ContractValidationError("rule_pins must be an array")
        pins = tuple(RulePin.from_dict(item) for item in raw_pins)
        if len({item.identity for item in pins}) != len(pins):
            raise ContractValidationError("rule_pins must not contain duplicates")
        try:
            status = EvidenceReadinessStatus(value.get("evidence_status"))
        except (TypeError, ValueError) as exc:
            raise ContractValidationError("unknown evidence_status") from exc
        item = cls(
            item_id=_text(value.get("item_id"), "item_id"),
            item_title=_text(value.get("item_title"), "item_title"),
            applicability_scope=_text(value.get("applicability_scope"), "applicability_scope"),
            project_control_keys=_strings(
                value.get("project_control_keys", ()), "project_control_keys"
            ),
            rule_pins=pins,
            automated_evidence_ids=_strings(
                value.get("automated_evidence_ids", ()), "automated_evidence_ids"
            ),
            missing_evidence=_strings(value.get("missing_evidence", ()), "missing_evidence"),
            finding_ids=_strings(value.get("finding_ids", ()), "finding_ids"),
            remediation_ids=_strings(value.get("remediation_ids", ()), "remediation_ids"),
            evidence_status=status,
        )
        item._validate_status()
        return item

    def _validate_status(self) -> None:
        if self.evidence_status is EvidenceReadinessStatus.AUTOMATED_EVIDENCE:
            if not self.automated_evidence_ids or self.missing_evidence:
                raise ContractValidationError(
                    "AUTOMATED_EVIDENCE requires evidence and no missing evidence"
                )
        if self.evidence_status is EvidenceReadinessStatus.PARTIAL_EVIDENCE:
            if not self.automated_evidence_ids or not self.missing_evidence:
                raise ContractValidationError(
                    "PARTIAL_EVIDENCE requires both obtained and missing evidence"
                )
        if self.evidence_status is EvidenceReadinessStatus.EVIDENCE_MISSING:
            if self.automated_evidence_ids or not self.missing_evidence:
                raise ContractValidationError(
                    "EVIDENCE_MISSING requires missing evidence and no obtained evidence"
                )
        if self.evidence_status is EvidenceReadinessStatus.MANUAL_REVIEW:
            if not self.missing_evidence:
                raise ContractValidationError("MANUAL_REVIEW must identify required evidence")
        if self.evidence_status is EvidenceReadinessStatus.OUT_OF_SCOPE:
            if any(
                (
                    self.project_control_keys,
                    self.rule_pins,
                    self.automated_evidence_ids,
                    self.finding_ids,
                    self.remediation_ids,
                )
            ):
                raise ContractValidationError("OUT_OF_SCOPE must not claim mapped implementation")

    @property
    def mapped(self) -> bool:
        return bool(self.project_control_keys)

    @property
    def manual_review_required(self) -> bool:
        return self.evidence_status in {
            EvidenceReadinessStatus.MANUAL_REVIEW,
            EvidenceReadinessStatus.PARTIAL_EVIDENCE,
            EvidenceReadinessStatus.EVIDENCE_MISSING,
        }


@dataclass(frozen=True)
class ComplianceReadinessSummary:
    source_id: str
    source_version: str
    selected_item_count: int
    mapped_item_count: int
    mapping_coverage: float | None
    evidence_status_counts: Mapping[str, int]
    items: tuple[ComplianceItemMapping, ...]
    interpretation: str = (
        "Mapping Coverage와 Evidence Readiness이며 준수율, 인증 점수 또는 "
        "인증 가능성 예측이 아니다."
    )


def build_compliance_readiness(
    *,
    source_id: str,
    source_version: str,
    selected_item_ids: Iterable[str],
    mappings: Iterable[ComplianceItemMapping],
) -> ComplianceReadinessSummary:
    selected = tuple(_text(item, "selected_item_id") for item in selected_item_ids)
    if len(set(selected)) != len(selected):
        raise ContractValidationError("selected_item_ids must not contain duplicates")
    mapping_items = tuple(mappings)
    mapping_index = {item.item_id: item for item in mapping_items}
    if len(mapping_index) != len(mapping_items):
        raise ContractValidationError("compliance item mappings must not contain duplicates")
    if not selected:
        return ComplianceReadinessSummary(
            source_id=_text(source_id, "source_id"),
            source_version=_text(source_version, "source_version"),
            selected_item_count=0,
            mapped_item_count=0,
            mapping_coverage=None,
            evidence_status_counts={},
            items=(),
        )
    missing = tuple(item for item in selected if item not in mapping_index)
    if missing:
        raise ContractValidationError(
            "selected compliance items have no readiness record: " + ", ".join(missing)
        )
    items = tuple(mapping_index[item] for item in selected)
    mapped_count = sum(item.mapped for item in items)
    counts = Counter(item.evidence_status.value for item in items)
    return ComplianceReadinessSummary(
        source_id=_text(source_id, "source_id"),
        source_version=_text(source_version, "source_version"),
        selected_item_count=len(items),
        mapped_item_count=mapped_count,
        mapping_coverage=round(mapped_count * 100.0 / len(items), 1),
        evidence_status_counts=dict(sorted(counts.items())),
        items=items,
    )
