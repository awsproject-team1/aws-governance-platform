"""Deterministic phase-specific Effective Rule Set construction."""

from __future__ import annotations

from packages.contracts.governance import (
    AdminSettingsSnapshotReference,
    EffectiveRuleSet,
    EvaluationType,
    PolicyProfile,
    RuleSetPhase,
)

from ..canonical import semantic_hash
from ..rules.registry import RuleRegistry

PHASE_EVALUATION_TYPES = {
    RuleSetPhase.INITIAL: frozenset({EvaluationType.IAC}),
    RuleSetPhase.PRE_DEPLOY: frozenset(
        {EvaluationType.IAC, EvaluationType.AWS, EvaluationType.HYBRID}
    ),
    RuleSetPhase.POST_DEPLOY: frozenset(
        {EvaluationType.IAC, EvaluationType.AWS, EvaluationType.HYBRID}
    ),
    RuleSetPhase.MANUAL_REVIEW: frozenset({EvaluationType.MANUAL}),
}


def build_effective_rule_set(
    profile: PolicyProfile,
    phase: RuleSetPhase,
    admin_settings: AdminSettingsSnapshotReference,
    rules: RuleRegistry,
) -> EffectiveRuleSet:
    """Build a new Assessment rule set; every pin must still be ACTIVE."""
    return _build_rule_set(profile, phase, admin_settings, rules, reproduce=False)


def reproduce_effective_rule_set(
    profile: PolicyProfile,
    phase: RuleSetPhase,
    admin_settings: AdminSettingsSnapshotReference,
    rules: RuleRegistry,
) -> EffectiveRuleSet:
    """Rebuild historical pins from immutable approval snapshots.

    A deprecated Rule cannot enter a new Assessment, but its approval-time snapshot must
    remain available to reproduce an Assessment that already pinned that version.
    """
    return _build_rule_set(profile, phase, admin_settings, rules, reproduce=True)


def _build_rule_set(
    profile: PolicyProfile,
    phase: RuleSetPhase,
    admin_settings: AdminSettingsSnapshotReference,
    rules: RuleRegistry,
    *,
    reproduce: bool,
) -> EffectiveRuleSet:
    selected = []
    for pin in profile.rule_pins:
        rule = (
            rules.approved_snapshot(pin.rule_id, pin.version).rule
            if reproduce
            else rules.active(pin.rule_id, pin.version)
        )
        if rule.evaluation_type in PHASE_EVALUATION_TYPES[phase]:
            selected.append(rule)
    selected.sort(key=lambda item: (item.rule_id, item.version))
    projection = {
        "policy_profile_id": profile.policy_profile_id,
        "policy_profile_version": profile.policy_profile_version,
        "phase": phase.value,
        "admin_settings_snapshot_hash": admin_settings.admin_settings_snapshot_hash,
        "rules": [item.to_dict() for item in selected],
    }
    return EffectiveRuleSet(
        policy_profile_id=profile.policy_profile_id,
        policy_profile_version=profile.policy_profile_version,
        phase=phase,
        admin_settings_snapshot_hash=admin_settings.admin_settings_snapshot_hash,
        rules=tuple(selected),
        rule_set_hash=semantic_hash(projection),
    )
