import json
import unittest
from copy import deepcopy
from pathlib import Path

from packages.contracts.governance import (
    AdminSettingsSnapshotReference,
    AssessmentPhase,
    Control,
    PolicyProfile,
    PolicySource,
    Rule,
    RuleApproval,
    RuleEvaluationMetric,
    RuleSetPhase,
    RuleStatus,
    SourceControlMapping,
)
from packages.governance.controls.registry import ControlRegistry
from packages.governance.errors import GovernanceNotFoundError, GovernanceValidationError
from packages.governance.mappings.registry import SourceControlMappingRegistry
from packages.governance.profiles.effective import (
    build_effective_rule_set,
    reproduce_effective_rule_set,
)
from packages.governance.profiles.registry import PolicyProfileRegistry
from packages.governance.rules.registry import RuleRegistry, rule_content_hash
from packages.governance.scoring.calculator import calculate_source_metrics
from packages.governance.sources.registry import PolicySourceRegistry

REPO = Path(__file__).resolve().parents[2]
RULE_FIXTURE = REPO / "fixtures" / "rules" / "governance-golden.json"
PROFILE_FIXTURE = REPO / "fixtures" / "profiles" / "governance-golden.json"
SCORING_FIXTURE = REPO / "fixtures" / "rules" / "scoring-golden.json"


def load_fixture(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_registries(include_rules=True):
    fixture = load_fixture(RULE_FIXTURE)
    controls = ControlRegistry([Control.from_dict(item) for item in fixture["controls"]])
    sources = PolicySourceRegistry(
        [PolicySource.from_dict(item) for item in fixture["policy_sources"]]
    )
    mappings = SourceControlMappingRegistry(
        controls,
        sources,
        [SourceControlMapping.from_dict(item) for item in fixture["mappings"]],
    )
    rules = RuleRegistry(mappings)
    for item in fixture["approvals"]:
        rules.add_approval(RuleApproval.from_dict(item))
    if include_rules:
        for item in fixture["rules"]:
            rules.add(Rule.from_dict(item))
    return fixture, controls, mappings, rules


class RegistryAndLifecycleTests(unittest.TestCase):
    def test_control_mapping_and_rule_registry_validate_golden_fixture(self):
        fixture, controls, mappings, rules = build_registries()
        self.assertEqual(len(controls.list()), 3)
        self.assertEqual(len(mappings.list()), 4)
        self.assertEqual(len(rules.list()), 4)
        self.assertEqual(len(fixture["policy_sources"]), 2)

    def test_active_rule_requires_matching_identity_and_content_approval(self):
        fixture, controls, mappings, rules = build_registries(include_rules=False)
        active = Rule.from_dict(fixture["rules"][0])
        registry_without_approval = RuleRegistry(mappings)
        with self.assertRaises(GovernanceValidationError):
            registry_without_approval.add(active)

        changed = deepcopy(fixture["rules"][0])
        changed["severity"] = "CRITICAL"
        with self.assertRaises(GovernanceValidationError):
            rules.add(Rule.from_dict(changed))

    def test_unknown_source_mapping_is_rejected(self):
        fixture, _, mappings, rules = build_registries(include_rules=False)
        rule = deepcopy(fixture["rules"][0])
        rule["source_references"][0]["section"] = "S3.UNKNOWN"
        with self.assertRaises(GovernanceNotFoundError):
            rules.add(Rule.from_dict(rule))

    def test_deprecation_preserves_identity_and_prevents_active_consumption(self):
        _, _, mappings, rules = build_registries()
        approved = rules.approved_snapshot("GLOBAL-S3-PAB-001", 1)
        deprecated = rules.deprecate(
            "GLOBAL-S3-PAB-001",
            1,
            deprecated_by="fixture-reviewer",
            deprecated_at="2026-08-26T00:00:00Z",
            reason="superseded by a reviewed version",
        )
        self.assertIs(deprecated.status, RuleStatus.DEPRECATED)
        self.assertEqual(deprecated.identity, ("GLOBAL-S3-PAB-001", 1))
        self.assertEqual(rule_content_hash(deprecated), approved.approval.rule_content_hash)
        self.assertIs(approved.rule.status, RuleStatus.ACTIVE)
        self.assertEqual(rules.audit_entries()[0].action, "DEPRECATED")
        with self.assertRaises(GovernanceValidationError):
            rules.active("GLOBAL-S3-PAB-001", 1)

        rehydrated = RuleRegistry(mappings)
        rehydrated.add_approval(rules.approval("GLOBAL-S3-PAB-001", 1))
        rehydrated.add(deprecated)
        restored = rehydrated.approved_snapshot("GLOBAL-S3-PAB-001", 1)
        self.assertIs(restored.rule.status, RuleStatus.ACTIVE)
        self.assertEqual(restored.approval.rule_content_hash, rule_content_hash(deprecated))


class ProfileAndEffectiveRuleSetTests(unittest.TestCase):
    def setUp(self):
        _, _, _, self.rules = build_registries()
        self.fixture = load_fixture(PROFILE_FIXTURE)
        self.profile = PolicyProfile.from_dict(self.fixture["profile"])
        self.settings = AdminSettingsSnapshotReference.from_dict(self.fixture["admin_settings"])

    def test_profile_pins_only_active_approved_versions(self):
        profiles = PolicyProfileRegistry(self.rules)
        profiles.add(self.profile)
        self.assertEqual(profiles.get(*self.profile.identity), self.profile)

    def test_phase_rule_selection_is_deterministic_and_preserves_settings(self):
        for raw_phase, expected in self.fixture["expected_rule_ids"].items():
            phase = RuleSetPhase(raw_phase)
            first = build_effective_rule_set(self.profile, phase, self.settings, self.rules)
            second = build_effective_rule_set(self.profile, phase, self.settings, self.rules)
            identities = [f"{rule.rule_id}@{rule.version}" for rule in first.rules]
            self.assertEqual(identities, expected)
            self.assertEqual(first, second)
            # 결정론적 재현의 기준은 선택된 Rule 목록이 아니라 rule_set_hash다.
            # 값을 고정하지 않으면 projection이 바뀌어도 이 test가 통과한다.
            self.assertEqual(
                first.rule_set_hash,
                self.fixture["expected_rule_set_hash"][raw_phase],
            )
            self.assertEqual(
                first.admin_settings_snapshot_hash,
                self.settings.admin_settings_snapshot_hash,
            )

    def test_manual_review_is_a_rule_set_mode_not_an_assessment_phase(self):
        self.assertNotIn("MANUAL_REVIEW", {phase.name for phase in AssessmentPhase})
        self.assertIsNone(RuleSetPhase.MANUAL_REVIEW.assessment_phase)
        for phase in AssessmentPhase:
            self.assertIs(RuleSetPhase.for_assessment(phase).assessment_phase, phase)

    def test_same_control_global_and_customer_rules_are_not_deduplicated(self):
        effective = build_effective_rule_set(
            self.profile, RuleSetPhase.PRE_DEPLOY, self.settings, self.rules
        )
        same_control = [
            rule for rule in effective.rules if rule.control_key == "s3.public_access_block.enabled"
        ]
        self.assertEqual(len(same_control), 2)
        self.assertEqual({rule.source_type.value for rule in same_control}, {"GLOBAL", "CUSTOMER"})

    def test_historical_effective_rule_set_reproduces_after_deprecation(self):
        before = build_effective_rule_set(
            self.profile, RuleSetPhase.PRE_DEPLOY, self.settings, self.rules
        )
        self.rules.deprecate(
            "GLOBAL-S3-PAB-001",
            1,
            deprecated_by="fixture-reviewer",
            deprecated_at="2026-08-26T00:00:00Z",
            reason="historical reproduction test",
        )
        with self.assertRaises(GovernanceValidationError):
            build_effective_rule_set(
                self.profile, RuleSetPhase.PRE_DEPLOY, self.settings, self.rules
            )
        reproduced = reproduce_effective_rule_set(
            self.profile, RuleSetPhase.PRE_DEPLOY, self.settings, self.rules
        )
        self.assertEqual(reproduced, before)


class ScoringTests(unittest.TestCase):
    def setUp(self):
        _, _, _, self.rules = build_registries()
        profile_fixture = load_fixture(PROFILE_FIXTURE)
        self.fixture = load_fixture(SCORING_FIXTURE)
        self.effective = build_effective_rule_set(
            PolicyProfile.from_dict(profile_fixture["profile"]),
            RuleSetPhase(self.fixture["rule_set_phase"]),
            AdminSettingsSnapshotReference.from_dict(profile_fixture["admin_settings"]),
            self.rules,
        )
        self.evaluations = [
            RuleEvaluationMetric.from_dict(item) for item in self.fixture["evaluations"]
        ]

    def test_source_score_and_coverage_match_golden_fixture(self):
        first = [
            item.to_dict() for item in calculate_source_metrics(self.evaluations, self.effective)
        ]
        second = [
            item.to_dict()
            for item in calculate_source_metrics(reversed(self.evaluations), self.effective)
        ]
        self.assertEqual(first, self.fixture["expected"])
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertFalse(any("overall" in key.casefold() for item in first for key in item))

    def test_score_is_severity_weighted_not_a_plain_pass_ratio(self):
        customer = next(
            item
            for item in calculate_source_metrics(self.evaluations, self.effective)
            if item.source_id == "cloud-infra-security-checklist"
        )
        plain_ratio = self.fixture["unweighted_customer_score_would_be"]
        self.assertNotEqual(customer.score, plain_ratio)
        self.assertEqual(customer.score, 58.3)

    def test_consumer_supplied_severity_cannot_reweight_the_score(self):
        tampered = deepcopy(self.fixture["evaluations"])
        tampered[3]["severity"] = "LOW"
        metrics = [RuleEvaluationMetric.from_dict(item) for item in tampered]
        with self.assertRaises(GovernanceValidationError):
            calculate_source_metrics(metrics, self.effective)

    def test_evaluation_outside_the_effective_rule_set_is_rejected(self):
        outside = deepcopy(self.fixture["evaluations"][0])
        outside["rule_id"] = "CUSTOMER-S3-PROC-001"
        outside["rule_version"] = 1
        outside["source_id"] = "cloud-infra-security-checklist"
        outside["source_type"] = "CUSTOMER"
        outside["severity"] = "LOW"
        with self.assertRaises(GovernanceValidationError):
            calculate_source_metrics([RuleEvaluationMetric.from_dict(outside)], self.effective)

    def test_source_id_must_be_a_validated_source_reference_of_the_rule(self):
        mismatched = deepcopy(self.fixture["evaluations"][0])
        mismatched["source_id"] = "cloud-infra-security-checklist"
        with self.assertRaises(GovernanceValidationError):
            calculate_source_metrics([RuleEvaluationMetric.from_dict(mismatched)], self.effective)

    def test_duplicate_metric_retransmission_is_rejected(self):
        duplicate = [self.evaluations[0], self.evaluations[0]]
        with self.assertRaisesRegex(GovernanceValidationError, "duplicate Resource"):
            calculate_source_metrics(duplicate, self.effective)

    def test_unknown_scoring_version_is_rejected(self):
        with self.assertRaisesRegex(GovernanceValidationError, "unsupported scoring_version"):
            calculate_source_metrics(
                self.evaluations,
                self.effective,
                scoring_version="2-unapproved",
            )


if __name__ == "__main__":
    unittest.main()
