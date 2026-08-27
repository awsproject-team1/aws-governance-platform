"""Verified Global Source definitions and immutable snapshot metadata.

The catalog deliberately separates an official reference definition from a frozen
snapshot. Finding an official URL is not enough to claim that a Source has a fixed
control set, approved Rules, or executable Assessment coverage.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from packages.contracts.governance import ContractValidationError, SourceType

from ..canonical import semantic_hash
from ..errors import GovernanceConflictError, GovernanceNotFoundError
from .ingestion import FrozenDocument


class GlobalSourceRole(str, Enum):
    SECURITY_BASELINE = "SECURITY_BASELINE"
    GOVERNANCE_HYGIENE = "GOVERNANCE_HYGIENE"
    CONDITIONAL_GOVERNANCE = "CONDITIONAL_GOVERNANCE"
    MAPPING_EVIDENCE = "MAPPING_EVIDENCE"


class SourceResultKind(str, Enum):
    SCORE_AND_COVERAGE = "SCORE_AND_COVERAGE"
    CONDITIONAL_CONTROL_COVERAGE = "CONDITIONAL_CONTROL_COVERAGE"
    MAPPING_AND_EVIDENCE_READINESS = "MAPPING_AND_EVIDENCE_READINESS"


_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ContractValidationError(f"{name} must be an array")
    result = tuple(_text(item, name) for item in value)
    if len(set(result)) != len(result):
        raise ContractValidationError(f"{name} must not contain duplicates")
    return result


def _official_url(value: Any) -> str:
    value = _text(value, "official_reference_url")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ContractValidationError("official_reference_url must be an https URL")
    return value


def _hash(value: Any, name: str) -> str:
    value = _text(value, name)
    if not _HASH_PATTERN.fullmatch(value):
        raise ContractValidationError(f"{name} must be a lowercase sha256 digest")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ContractValidationError(f"{name} must be a boolean")
    return value


@dataclass(frozen=True)
class GlobalSourceDefinition:
    source_id: str
    publisher: str
    framework_version: str | None
    official_reference_url: str
    verified_at: str
    role: GlobalSourceRole
    result_kind: SourceResultKind
    score_label: str | None
    default_profile_eligible: bool
    required_capabilities: tuple[str, ...]
    global_evaluation_scope: tuple[str, ...]
    customer_defined_scope: tuple[str, ...]
    version_strategy: str
    delivery_or_mapping_reference: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> GlobalSourceDefinition:
        try:
            role = GlobalSourceRole(value.get("role"))
            result_kind = SourceResultKind(value.get("result_kind"))
        except (TypeError, ValueError) as exc:
            raise ContractValidationError("unknown Global Source role or result_kind") from exc
        item = cls(
            source_id=_text(value.get("source_id"), "source_id"),
            publisher=_text(value.get("publisher"), "publisher"),
            framework_version=_optional_text(value.get("framework_version"), "framework_version"),
            official_reference_url=_official_url(value.get("official_reference_url")),
            verified_at=_text(value.get("verified_at"), "verified_at"),
            role=role,
            result_kind=result_kind,
            score_label=_optional_text(value.get("score_label"), "score_label"),
            default_profile_eligible=_boolean(
                value.get("default_profile_eligible"), "default_profile_eligible"
            ),
            required_capabilities=_strings(
                value.get("required_capabilities", ()), "required_capabilities"
            ),
            global_evaluation_scope=_strings(
                value.get("global_evaluation_scope", ()), "global_evaluation_scope"
            ),
            customer_defined_scope=_strings(
                value.get("customer_defined_scope", ()), "customer_defined_scope"
            ),
            version_strategy=_text(value.get("version_strategy"), "version_strategy"),
            delivery_or_mapping_reference=_optional_text(
                value.get("delivery_or_mapping_reference"),
                "delivery_or_mapping_reference",
            ),
        )
        item._validate_policy()
        return item

    def _validate_policy(self) -> None:
        if self.result_kind is SourceResultKind.SCORE_AND_COVERAGE and self.score_label is None:
            raise ContractValidationError(
                "scored Global Source requires a non-official score label"
            )
        if self.result_kind is not SourceResultKind.SCORE_AND_COVERAGE and self.score_label:
            raise ContractValidationError("non-scored Source must not declare a score label")
        prohibited = ("official", "공식", "compliance score", "인증 점수", "준수율")
        if self.score_label and any(term in self.score_label.casefold() for term in prohibited):
            raise ContractValidationError(
                "score label must not imply an official or compliance score"
            )
        if self.role is GlobalSourceRole.MAPPING_EVIDENCE:
            if self.result_kind is not SourceResultKind.MAPPING_AND_EVIDENCE_READINESS:
                raise ContractValidationError("mapping-only Source requires readiness result kind")
            if self.default_profile_eligible:
                raise ContractValidationError("mapping-only Source cannot enter a Policy Profile")
        if self.role is GlobalSourceRole.CONDITIONAL_GOVERNANCE:
            if self.default_profile_eligible or not self.required_capabilities:
                raise ContractValidationError(
                    "conditional Source requires capabilities and cannot be default"
                )


@dataclass(frozen=True)
class SourceApplicability:
    source_id: str
    applicable: bool
    missing_capabilities: tuple[str, ...]


class GlobalSourceCatalog:
    def __init__(self, definitions: Iterable[GlobalSourceDefinition] = ()) -> None:
        self._definitions: dict[str, GlobalSourceDefinition] = {}
        for definition in definitions:
            self.add(definition)

    def add(self, definition: GlobalSourceDefinition) -> None:
        if definition.source_id in self._definitions:
            raise GovernanceConflictError(f"duplicate Global Source: {definition.source_id}")
        self._definitions[definition.source_id] = definition

    def get(self, source_id: str) -> GlobalSourceDefinition:
        try:
            return self._definitions[source_id]
        except KeyError as exc:
            raise GovernanceNotFoundError(f"unknown Global Source: {source_id}") from exc

    def applicability(
        self, source_id: str, customer_capabilities: Iterable[str]
    ) -> SourceApplicability:
        definition = self.get(source_id)
        capabilities = frozenset(customer_capabilities)
        missing = tuple(
            item for item in definition.required_capabilities if item not in capabilities
        )
        return SourceApplicability(
            source_id=source_id,
            applicable=not missing,
            missing_capabilities=missing,
        )

    def default_profile_candidates(self) -> tuple[GlobalSourceDefinition, ...]:
        """Return reference-level candidates, not executable Profile membership."""
        return tuple(
            item
            for item in self.list()
            if item.default_profile_eligible and item.role is not GlobalSourceRole.MAPPING_EVIDENCE
        )

    def list(self) -> tuple[GlobalSourceDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))


@dataclass(frozen=True)
class ExcludedControl:
    control_id: str
    reason: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ExcludedControl:
        return cls(
            control_id=_text(value.get("control_id"), "control_id"),
            reason=_text(value.get("reason"), "reason"),
        )


@dataclass(frozen=True)
class FrozenGlobalSourceSnapshot:
    source_id: str
    source_version: str
    framework_version: str | None
    snapshot_date: str
    collected_at: str
    official_reference_url: str
    canonical_content_hash: str
    selected_control_ids: tuple[str, ...]
    excluded_controls: tuple[ExcludedControl, ...]
    mapping_version: str
    control_set_hash: str

    @classmethod
    def from_frozen_document(
        cls,
        document: FrozenDocument,
        definition: GlobalSourceDefinition,
        *,
        snapshot_date: str,
        collected_at: str,
        selected_control_ids: Iterable[str],
        excluded_controls: Iterable[ExcludedControl],
        mapping_version: str,
    ) -> FrozenGlobalSourceSnapshot:
        """Derive identity and canonical hash from a server-held frozen document."""
        if document.source_type is not SourceType.GLOBAL:
            raise ContractValidationError("Global Source snapshot requires a GLOBAL document")
        if document.document_id != definition.source_id:
            raise ContractValidationError("frozen document differs from catalog source_id")
        canonical_content_hash = semantic_hash(
            {
                "sections": [
                    {
                        "section": section.section,
                        "content_hash": section.content_hash,
                    }
                    for section in document.sections
                ]
            }
        )
        return cls.create(
            source_id=document.document_id,
            source_version=document.document_version,
            framework_version=definition.framework_version,
            snapshot_date=snapshot_date,
            collected_at=collected_at,
            official_reference_url=definition.official_reference_url,
            canonical_content_hash=canonical_content_hash,
            selected_control_ids=selected_control_ids,
            excluded_controls=excluded_controls,
            mapping_version=mapping_version,
        )

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        source_version: str,
        framework_version: str | None,
        snapshot_date: str,
        collected_at: str,
        official_reference_url: str,
        canonical_content_hash: str,
        selected_control_ids: Iterable[str],
        excluded_controls: Iterable[ExcludedControl],
        mapping_version: str,
    ) -> FrozenGlobalSourceSnapshot:
        """Rehydrate trusted snapshot fields; normal ingestion uses from_frozen_document."""
        raw_selected = tuple(_text(item, "selected_control_id") for item in selected_control_ids)
        if len(set(raw_selected)) != len(raw_selected):
            raise ContractValidationError("selected control IDs must not contain duplicates")
        selected = tuple(sorted(raw_selected))
        excluded = tuple(sorted(excluded_controls, key=lambda item: item.control_id))
        if len({item.control_id for item in excluded}) != len(excluded):
            raise ContractValidationError("excluded control IDs must not contain duplicates")
        if not selected:
            raise ContractValidationError("frozen Global Source requires selected controls")
        overlap = set(selected).intersection(item.control_id for item in excluded)
        if overlap:
            raise ContractValidationError("a control cannot be both selected and excluded")
        projection = {
            "source_id": _text(source_id, "source_id"),
            "source_version": _text(source_version, "source_version"),
            "framework_version": _optional_text(framework_version, "framework_version"),
            "snapshot_date": _text(snapshot_date, "snapshot_date"),
            "selected_control_ids": list(selected),
            "excluded_controls": [
                {"control_id": item.control_id, "reason": item.reason} for item in excluded
            ],
            "mapping_version": _text(mapping_version, "mapping_version"),
        }
        return cls(
            source_id=projection["source_id"],
            source_version=projection["source_version"],
            framework_version=projection["framework_version"],
            snapshot_date=projection["snapshot_date"],
            collected_at=_text(collected_at, "collected_at"),
            official_reference_url=_official_url(official_reference_url),
            canonical_content_hash=_hash(canonical_content_hash, "canonical_content_hash"),
            selected_control_ids=selected,
            excluded_controls=excluded,
            mapping_version=projection["mapping_version"],
            control_set_hash=semantic_hash(projection),
        )

    @property
    def identity(self) -> tuple[str, str]:
        return (self.source_id, self.source_version)


@dataclass(frozen=True)
class SourceSnapshotChange:
    source_id: str
    previous_version: str
    current_version: str
    added_control_ids: tuple[str, ...]
    removed_control_ids: tuple[str, ...]
    content_changed: bool
    mapping_changed: bool


class GlobalSourceSnapshotRegistry:
    def __init__(self, catalog: GlobalSourceCatalog) -> None:
        self._catalog = catalog
        self._snapshots: dict[tuple[str, str], FrozenGlobalSourceSnapshot] = {}

    def freeze(self, snapshot: FrozenGlobalSourceSnapshot) -> None:
        definition = self._catalog.get(snapshot.source_id)
        if snapshot.framework_version != definition.framework_version:
            raise ContractValidationError("snapshot framework_version differs from catalog")
        if snapshot.official_reference_url != definition.official_reference_url:
            raise ContractValidationError("snapshot official reference differs from catalog")
        if snapshot.identity in self._snapshots:
            raise GovernanceConflictError(
                f"duplicate Global Source snapshot: {snapshot.source_id}@{snapshot.source_version}"
            )
        self._snapshots[snapshot.identity] = snapshot

    def get(self, source_id: str, source_version: str) -> FrozenGlobalSourceSnapshot:
        try:
            return self._snapshots[(source_id, source_version)]
        except KeyError as exc:
            raise GovernanceNotFoundError(
                f"unknown Global Source snapshot: {source_id}@{source_version}"
            ) from exc

    @staticmethod
    def compare(
        previous: FrozenGlobalSourceSnapshot,
        current: FrozenGlobalSourceSnapshot,
    ) -> SourceSnapshotChange:
        if previous.source_id != current.source_id:
            raise ContractValidationError("cannot compare snapshots from different sources")
        previous_controls = set(previous.selected_control_ids)
        current_controls = set(current.selected_control_ids)
        return SourceSnapshotChange(
            source_id=current.source_id,
            previous_version=previous.source_version,
            current_version=current.source_version,
            added_control_ids=tuple(sorted(current_controls - previous_controls)),
            removed_control_ids=tuple(sorted(previous_controls - current_controls)),
            content_changed=previous.canonical_content_hash != current.canonical_content_hash,
            mapping_changed=previous.mapping_version != current.mapping_version,
        )
