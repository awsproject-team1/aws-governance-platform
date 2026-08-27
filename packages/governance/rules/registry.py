"""Rule identity, immutable approval snapshots, lifecycle, and mapping validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from packages.contracts.governance import Rule, RuleApproval, RuleStatus, SourceType

from ..canonical import semantic_hash
from ..errors import GovernanceConflictError, GovernanceNotFoundError, GovernanceValidationError
from ..mappings.registry import SourceControlMappingRegistry


def rule_semantic_content(rule: Rule) -> Mapping[str, Any]:
    """Approval 대상 의미 내용.

    ``rule_id``와 ``version``은 :class:`RuleApproval` identity가 별도로 묶고,
    ``status``는 승인 뒤에도 바뀔 수 있는 lifecycle metadata다. 이 셋을 semantic
    content에서 제외해야 DEPRECATED 뒤에도 승인 당시 의미를 재현할 수 있다.
    """
    content = rule.to_dict()
    for field in ("rule_id", "version", "status"):
        content.pop(field)
    return content


def rule_content_hash(rule: Rule) -> str:
    return semantic_hash(rule_semantic_content(rule))


@dataclass(frozen=True)
class ApprovedRuleSnapshot:
    rule: Rule
    approval: RuleApproval

    def __post_init__(self) -> None:
        if self.rule.identity != self.approval.identity:
            raise GovernanceValidationError("approved snapshot identity does not match approval")
        if self.approval.rule_content_hash != rule_content_hash(self.rule):
            raise GovernanceValidationError("approved snapshot content does not match approval")


@dataclass(frozen=True)
class RuleAuditEntry:
    rule_id: str
    version: int
    action: str
    actor: str
    occurred_at: str
    rule_content_hash: str
    reason: str | None = None


class RuleRegistry:
    def __init__(self, mappings: SourceControlMappingRegistry) -> None:
        self._mappings = mappings
        self._rules: dict[tuple[str, int], Rule] = {}
        self._approvals: dict[tuple[str, int], RuleApproval] = {}
        self._approved_snapshots: dict[tuple[str, int], ApprovedRuleSnapshot] = {}
        self._audit: list[RuleAuditEntry] = []

    def add_approval(self, approval: RuleApproval) -> None:
        if approval.identity in self._approvals:
            raise GovernanceConflictError(f"duplicate approval: {approval.identity}")
        self._approvals[approval.identity] = approval

    def _validate(self, rule: Rule, approval: RuleApproval | None = None) -> None:
        if rule.identity in self._rules:
            raise GovernanceConflictError(f"duplicate rule identity: {rule.identity}")
        expected_prefix = "GLOBAL-" if rule.source_type is SourceType.GLOBAL else "CUSTOMER-"
        if not rule.rule_id.startswith(expected_prefix):
            raise GovernanceValidationError("rule_id prefix must match source_type")
        for reference in rule.source_references:
            self._mappings.require(reference, rule.resource_type, rule.control_key)
            if self._mappings.source_type(reference) is not rule.source_type:
                raise GovernanceValidationError(
                    "rule source_type does not match its registered Policy Source"
                )
        approval = approval or self._approvals.get(rule.identity)
        if approval is None:
            raise GovernanceValidationError(
                f"{rule.status.value} rule requires rule_id + version approval"
            )
        if approval.rule_content_hash != rule_content_hash(rule):
            raise GovernanceValidationError(
                f"{rule.status.value} rule content does not match its approval"
            )

    def add(self, rule: Rule) -> None:
        """영속 저장소에서 Rule/Approval을 복원하는 저수준 경계."""
        self._validate(rule)
        self._rules[rule.identity] = rule
        approved_rule = (
            rule if rule.status is RuleStatus.ACTIVE else replace(rule, status=RuleStatus.ACTIVE)
        )
        self._approved_snapshots[rule.identity] = ApprovedRuleSnapshot(
            rule=approved_rule,
            approval=self._approvals[rule.identity],
        )

    def activate(
        self,
        rule: Rule,
        *,
        approved_by: str,
        approved_at: str,
    ) -> ApprovedRuleSnapshot:
        """정확한 snapshot 승인과 ACTIVE 등록을 한 Domain 작업으로 수행한다."""
        if rule.status is not RuleStatus.ACTIVE:
            raise GovernanceValidationError("activation requires an ACTIVE rule snapshot")
        if rule.identity in self._approvals:
            raise GovernanceConflictError(f"duplicate approval: {rule.identity}")
        approval = RuleApproval.from_dict(
            {
                "rule_id": rule.rule_id,
                "version": rule.version,
                "rule_content_hash": rule_content_hash(rule),
                "approved_by": approved_by,
                "approved_at": approved_at,
            }
        )
        self._validate(rule, approval)
        snapshot = ApprovedRuleSnapshot(rule=rule, approval=approval)
        self._approvals[rule.identity] = approval
        self._rules[rule.identity] = rule
        self._approved_snapshots[rule.identity] = snapshot
        self._audit.append(
            RuleAuditEntry(
                rule_id=rule.rule_id,
                version=rule.version,
                action="APPROVED_AND_ACTIVATED",
                actor=approved_by,
                occurred_at=approved_at,
                rule_content_hash=approval.rule_content_hash,
            )
        )
        return snapshot

    def get(self, rule_id: str, version: int) -> Rule:
        try:
            return self._rules[(rule_id, version)]
        except KeyError as exc:
            raise GovernanceNotFoundError(f"unknown rule pin: {rule_id}@{version}") from exc

    def active(self, rule_id: str, version: int) -> Rule:
        rule = self.get(rule_id, version)
        if rule.status is not RuleStatus.ACTIVE:
            raise GovernanceValidationError(f"rule is not ACTIVE: {rule_id}@{version}")
        return rule

    def deprecate(
        self,
        rule_id: str,
        version: int,
        *,
        deprecated_by: str,
        deprecated_at: str,
        reason: str,
    ) -> Rule:
        if not deprecated_by.strip() or not deprecated_at.strip() or not reason.strip():
            raise GovernanceValidationError(
                "deprecation requires actor, timestamp, and non-empty reason"
            )
        rule = self.active(rule_id, version)
        deprecated = replace(rule, status=RuleStatus.DEPRECATED)
        self._rules[rule.identity] = deprecated
        approval = self.approval(rule_id, version)
        self._audit.append(
            RuleAuditEntry(
                rule_id=rule_id,
                version=version,
                action="DEPRECATED",
                actor=deprecated_by,
                occurred_at=deprecated_at,
                rule_content_hash=approval.rule_content_hash,
                reason=reason,
            )
        )
        return deprecated

    def approval(self, rule_id: str, version: int) -> RuleApproval:
        try:
            return self._approvals[(rule_id, version)]
        except KeyError as exc:
            raise GovernanceNotFoundError(f"approval not found: {rule_id}@{version}") from exc

    def approved_snapshot(self, rule_id: str, version: int) -> ApprovedRuleSnapshot:
        try:
            return self._approved_snapshots[(rule_id, version)]
        except KeyError as exc:
            raise GovernanceNotFoundError(
                f"approved rule snapshot not found: {rule_id}@{version}"
            ) from exc

    def next_version(self, rule_id: str) -> int:
        versions = [version for existing_id, version in self._rules if existing_id == rule_id]
        return max(versions, default=0) + 1

    def versions(self, rule_id: str) -> tuple[Rule, ...]:
        return tuple(self._rules[key] for key in sorted(self._rules) if key[0] == rule_id)

    def audit_entries(self, rule_id: str | None = None) -> tuple[RuleAuditEntry, ...]:
        entries = self._audit
        if rule_id is not None:
            entries = [item for item in entries if item.rule_id == rule_id]
        return tuple(entries)

    def list(self) -> tuple[Rule, ...]:
        return tuple(self._rules[key] for key in sorted(self._rules))
