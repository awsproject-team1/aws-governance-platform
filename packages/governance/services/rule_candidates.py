"""Safe application boundary for Candidate creation, review, and Rule activation.

Authentication/RBAC and persistence belong to Area A. This service assumes its caller
already authenticated the human reviewer, while still refusing identity/lifecycle values
from the untrusted structured Candidate payload.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from packages.contracts.governance import Rule

from ..errors import GovernanceValidationError
from ..mappings.registry import SourceControlMappingRegistry
from ..rules.candidates import (
    RuleCandidate,
    RuleCandidateRegistry,
    RuleCandidateValidation,
    validate_rule_candidate,
)
from ..rules.registry import ApprovedRuleSnapshot, RuleRegistry
from ..sources.ingestion import FrozenDocument


class RuleCandidateApplicationService:
    def __init__(
        self,
        candidates: RuleCandidateRegistry,
        rules: RuleRegistry,
        mappings: SourceControlMappingRegistry,
    ) -> None:
        self._candidates = candidates
        self._rules = rules
        self._mappings = mappings

    def create(
        self,
        candidate_id: str,
        payload: Mapping[str, Any],
        frozen_sources: Iterable[tuple[FrozenDocument, str]],
    ) -> RuleCandidateValidation:
        result = validate_rule_candidate(
            candidate_id,
            payload,
            frozen_sources,
            self._mappings,
        )
        if result.candidate is not None:
            self._candidates.add(result.candidate)
        return result

    def approve(
        self,
        candidate_id: str,
        *,
        server_rule_id: str,
        approved_by: str,
        approved_at: str,
    ) -> ApprovedRuleSnapshot:
        """Assign server-owned identity/version and atomically approve + activate."""
        candidate = self._candidates.get(candidate_id)
        if self._candidates.approved_rule(candidate_id) is not None:
            raise GovernanceValidationError("candidate has already produced an approved Rule")
        if not candidate.can_be_approved:
            raise GovernanceValidationError(
                "candidate has unresolved limitations or unconfirmed source extraction"
            )
        rule = self._active_rule(candidate, server_rule_id)
        snapshot = self._rules.activate(
            rule,
            approved_by=approved_by,
            approved_at=approved_at,
        )
        self._candidates.bind_approved_rule(candidate_id, rule.identity)
        return snapshot

    def _active_rule(self, candidate: RuleCandidate, server_rule_id: str) -> Rule:
        payload = dict(candidate.normalized_rule_fields)
        payload.update(
            {
                "rule_id": server_rule_id,
                "version": self._rules.next_version(server_rule_id),
                "status": "ACTIVE",
            }
        )
        return Rule.from_dict(payload)
