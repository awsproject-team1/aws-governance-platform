"""Version-pinned Policy Profile registry."""

from __future__ import annotations

from packages.contracts.governance import PolicyProfile

from ..errors import GovernanceConflictError, GovernanceNotFoundError
from ..rules.registry import RuleRegistry


class PolicyProfileRegistry:
    def __init__(self, rules: RuleRegistry) -> None:
        self._rules = rules
        self._profiles: dict[tuple[str, int], PolicyProfile] = {}

    def add(self, profile: PolicyProfile) -> None:
        if profile.identity in self._profiles:
            raise GovernanceConflictError(f"duplicate profile identity: {profile.identity}")
        for pin in profile.rule_pins:
            self._rules.active(pin.rule_id, pin.version)
        self._profiles[profile.identity] = profile

    def get(self, policy_profile_id: str, policy_profile_version: int) -> PolicyProfile:
        try:
            return self._profiles[(policy_profile_id, policy_profile_version)]
        except KeyError as exc:
            raise GovernanceNotFoundError(
                f"unknown policy profile: {policy_profile_id}@{policy_profile_version}"
            ) from exc

    def versions(self, policy_profile_id: str) -> tuple[PolicyProfile, ...]:
        return tuple(
            self._profiles[key] for key in sorted(self._profiles) if key[0] == policy_profile_id
        )

    def list(self) -> tuple[PolicyProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))
