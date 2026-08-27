import json
import unittest
from pathlib import Path

from packages.contracts.governance import (
    AdminSettingsSnapshotReference,
    AssessmentPhase,
    Control,
    EffectiveRuleSet,
    PolicyAnswer,
    PolicyEvidence,
    PolicyProfile,
    PolicyQuestion,
    PolicySource,
    Rule,
    RuleApproval,
    RuleEvaluationMetric,
    RuleSetPhase,
    SourceControlMapping,
    SourceReference,
)
from packages.governance.controls.registry import ControlRegistry
from packages.governance.mappings.registry import SourceControlMappingRegistry
from packages.governance.profiles.effective import (
    build_effective_rule_set,
    reproduce_effective_rule_set,
)
from packages.governance.rules.registry import RuleRegistry, rule_content_hash
from packages.governance.scoring.calculator import calculate_source_metrics
from packages.governance.sources.catalog import GlobalSourceCatalog, GlobalSourceDefinition
from packages.governance.sources.official_snapshot import FrozenOfficialControlSet
from packages.governance.sources.registry import PolicySourceRegistry

REPO = Path(__file__).resolve().parents[2]


class GovernanceToAssessmentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rule_fixture = json.loads(
            (REPO / "fixtures" / "rules" / "governance-golden.json").read_text(encoding="utf-8")
        )
        cls.profile_fixture = json.loads(
            (REPO / "fixtures" / "profiles" / "governance-golden.json").read_text(encoding="utf-8")
        )
        controls = ControlRegistry(
            [Control.from_dict(item) for item in cls.rule_fixture["controls"]]
        )
        sources = PolicySourceRegistry(
            [PolicySource.from_dict(item) for item in cls.rule_fixture["policy_sources"]]
        )
        mappings = SourceControlMappingRegistry(
            controls,
            sources,
            [SourceControlMapping.from_dict(item) for item in cls.rule_fixture["mappings"]],
        )
        cls.rules = RuleRegistry(mappings)
        for item in cls.rule_fixture["approvals"]:
            cls.rules.add_approval(RuleApproval.from_dict(item))
        for item in cls.rule_fixture["rules"]:
            cls.rules.add(Rule.from_dict(item))

    def test_effective_rule_set_is_stable_structured_input_for_area_c(self):
        profile = PolicyProfile.from_dict(self.profile_fixture["profile"])
        settings = AdminSettingsSnapshotReference.from_dict(self.profile_fixture["admin_settings"])
        effective = build_effective_rule_set(
            profile, RuleSetPhase.PRE_DEPLOY, settings, self.rules
        ).to_dict()
        self.assertEqual(effective["policy_profile_version"], 1)
        self.assertEqual(effective["phase"], "PRE_DEPLOY")
        self.assertRegex(effective["rule_set_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(len(effective["rules"]), 3)
        for rule in effective["rules"]:
            self.assertIsInstance(rule["version"], int)
            self.assertIn(rule["evaluation_type"], {"IAC", "AWS", "HYBRID"})
            self.assertIn(rule["severity"], {"CRITICAL", "HIGH", "MEDIUM", "LOW"})
            self.assertTrue(rule["source_references"])
            self.assertEqual(rule["status"], "ACTIVE")
        self.assertEqual(EffectiveRuleSet.from_dict(effective).to_dict(), effective)

    def test_reference_only_global_sources_do_not_enter_area_c_rule_set(self):
        catalog_fixture = json.loads(
            (REPO / "fixtures" / "policy" / "global-source-catalog.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(catalog_fixture["not_a_frozen_snapshot"])
        catalog = GlobalSourceCatalog(
            GlobalSourceDefinition.from_dict(item) for item in catalog_fixture["definitions"]
        )
        self.assertEqual(len(catalog.list()), 5)

        profile = PolicyProfile.from_dict(self.profile_fixture["profile"])
        settings = AdminSettingsSnapshotReference.from_dict(self.profile_fixture["admin_settings"])
        effective = build_effective_rule_set(profile, RuleSetPhase.PRE_DEPLOY, settings, self.rules)
        delivered_sources = {
            reference.document_id
            for rule in effective.rules
            for reference in rule.source_references
        }
        self.assertNotIn("cis-aws-foundations-5-0-0", delivered_sources)
        self.assertNotIn("aws-resource-tagging-1-0-0", delivered_sources)
        self.assertNotIn("aws-control-tower-controls", delivered_sources)
        self.assertNotIn("isms-p-2023-11-23", delivered_sources)

    def test_rule_set_phase_maps_onto_the_assessment_phase_area_c_stores(self):
        """C가 EffectiveRuleSet.phase를 Assessment.phase로 옮길 때의 경계."""
        profile = PolicyProfile.from_dict(self.profile_fixture["profile"])
        settings = AdminSettingsSnapshotReference.from_dict(self.profile_fixture["admin_settings"])
        for phase in AssessmentPhase:
            effective = build_effective_rule_set(
                profile, RuleSetPhase.for_assessment(phase), settings, self.rules
            )
            self.assertIs(effective.phase.assessment_phase, phase)

        manual = build_effective_rule_set(profile, RuleSetPhase.MANUAL_REVIEW, settings, self.rules)
        self.assertIsNone(manual.phase.assessment_phase)
        self.assertNotIn(manual.phase.value, {item.value for item in AssessmentPhase})

    def test_same_control_source_rules_are_separate_consumer_records(self):
        profile = PolicyProfile.from_dict(self.profile_fixture["profile"])
        settings = AdminSettingsSnapshotReference.from_dict(self.profile_fixture["admin_settings"])
        effective = build_effective_rule_set(profile, RuleSetPhase.PRE_DEPLOY, settings, self.rules)
        grouped = [
            rule for rule in effective.rules if rule.control_key == "s3.public_access_block.enabled"
        ]
        self.assertEqual(len(grouped), 2)
        self.assertEqual(len({rule.identity for rule in grouped}), 2)
        self.assertEqual(len({rule.source_type for rule in grouped}), 2)

    def test_manual_rule_is_not_delivered_as_automatically_evaluable(self):
        profile = PolicyProfile.from_dict(self.profile_fixture["profile"])
        settings = AdminSettingsSnapshotReference.from_dict(self.profile_fixture["admin_settings"])
        initial = build_effective_rule_set(profile, RuleSetPhase.INITIAL, settings, self.rules)
        self.assertNotIn("MANUAL", {rule.evaluation_type.value for rule in initial.rules})

    def test_evidence_reference_is_structured_for_assessment_and_remediation_consumers(self):
        fixture = json.loads(
            (REPO / "fixtures" / "policy" / "evidence-golden.json").read_text(encoding="utf-8")
        )
        evidence = PolicyEvidence.from_dict(fixture["evidence"][0]).to_dict()
        self.assertEqual(evidence["source_reference"]["document_id"], "aws-fsbp-1-0-0")
        self.assertRegex(evidence["source_reference"]["content_hash"], r"^sha256:")
        self.assertTrue(evidence["locator"])

        question = PolicyQuestion.from_dict(fixture["question"])
        answer = PolicyAnswer.from_dict(fixture["answer"])
        self.assertIn("aws-fsbp-1-0-0", question.allowed_source_ids)
        self.assertEqual(answer.evidence[0].source_reference.document_id, "aws-fsbp-1-0-0")
        self.assertTrue(answer.limitations)

    def test_rule_evidence_handoff_can_be_traced_by_finding_consumers(self):
        fixture = json.loads(
            (REPO / "fixtures" / "policy" / "rule-evidence-handoff.json").read_text(
                encoding="utf-8"
            )
        )
        rule_pin = fixture["rule_pin"]
        rule = self.rules.get(rule_pin["rule_id"], rule_pin["version"])
        evidence = PolicyEvidence.from_dict(fixture["policy_evidence"])
        self.assertIn(evidence.source_reference, rule.source_references)
        self.assertEqual(rule.identity, (rule_pin["rule_id"], rule_pin["version"]))
        self.assertNotIn("evaluation_status", fixture)
        self.assertNotIn("remediation", fixture)

    def test_s3_contract_proposal_uses_existing_shapes_and_blocks_unapproved_rebinding(self):
        proposal = json.loads(
            (REPO / "fixtures" / "assessments" / "s3-fsbp-b-to-c-proposal.json").read_text(
                encoding="utf-8"
            )
        )
        catalog_fixture = json.loads(
            (REPO / "fixtures" / "policy" / "global-source-catalog.json").read_text(
                encoding="utf-8"
            )
        )
        catalog = GlobalSourceCatalog(
            GlobalSourceDefinition.from_dict(item) for item in catalog_fixture["definitions"]
        )
        snapshot_fixture = json.loads(
            (REPO / "fixtures" / "policy" / "aws-fsbp-s3-official-snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        control_set = FrozenOfficialControlSet.from_dict(
            snapshot_fixture,
            catalog.get("aws-fsbp-1-0-0"),
        )

        approved = SourceReference.from_dict(proposal["approved_source_reference"])
        current = SourceReference.from_dict(
            proposal["official_revalidation"]["current_source_reference"]
        )
        rule_pin = proposal["rule_pin"]
        rule = self.rules.get(rule_pin["rule_id"], rule_pin["version"])
        self.assertIn(approved, rule.source_references)
        self.assertNotIn(current, rule.source_references)
        self.assertEqual(current, control_set.source_reference_for("S3.8"))
        self.assertFalse(proposal["execution_gate"]["deliver_as_officially_revalidated_rule"])
        self.assertTrue(
            proposal["official_revalidation"]["requires_new_rule_version_and_human_approval"]
        )
        self.assertEqual(proposal["shared_contract_changes"], [])

    def test_s3_metric_examples_round_trip_and_score_with_existing_contract(self):
        proposal = json.loads(
            (REPO / "fixtures" / "assessments" / "s3-fsbp-b-to-c-proposal.json").read_text(
                encoding="utf-8"
            )
        )
        profile = PolicyProfile.from_dict(self.profile_fixture["profile"])
        settings = AdminSettingsSnapshotReference.from_dict(self.profile_fixture["admin_settings"])
        effective = build_effective_rule_set(
            profile,
            RuleSetPhase.PRE_DEPLOY,
            settings,
            self.rules,
        )
        self.assertEqual(
            {
                item["case"]
                for item in proposal["metric_shape_examples_for_existing_v1_contract_only"]
            },
            {"positive", "negative", "tool_error"},
        )
        for example in proposal["metric_shape_examples_for_existing_v1_contract_only"]:
            metric = RuleEvaluationMetric.from_dict(example["metric"])
            self.assertEqual(metric.to_dict(), example["metric"])
            result = calculate_source_metrics((metric,), effective)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].to_dict(), example["expected_source_metric"])

    def test_sg_vpc_inventory_cannot_be_mistaken_for_rule_candidates(self):
        inventory = json.loads(
            (REPO / "fixtures" / "rules" / "fsbp-sg-vpc-source-inventory.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(inventory["candidate_creation_allowed"])
        prohibited = set(inventory["fields_intentionally_absent_until_review"])
        for group in ("security_group_source_inventory", "vpc_source_inventory"):
            for item in inventory[group]:
                self.assertTrue(prohibited.isdisjoint(item))

    def test_source_rule_and_profile_versions_remain_reproducible(self):
        controls = ControlRegistry(
            [Control.from_dict(item) for item in self.rule_fixture["controls"]]
        )
        source_items = [
            PolicySource.from_dict(item) for item in self.rule_fixture["policy_sources"]
        ]
        source_items.append(
            PolicySource.from_dict(
                {
                    "source_id": "cloud-infra-security-checklist",
                    "source_type": "CUSTOMER",
                    "source_version": "2026.09",
                }
            )
        )
        sources = PolicySourceRegistry(source_items)
        mappings = SourceControlMappingRegistry(
            controls,
            sources,
            [SourceControlMapping.from_dict(item) for item in self.rule_fixture["mappings"]],
        )
        rules = RuleRegistry(mappings)
        for item in self.rule_fixture["approvals"]:
            rules.add_approval(RuleApproval.from_dict(item))
        for item in self.rule_fixture["rules"]:
            rules.add(Rule.from_dict(item))
        profile = PolicyProfile.from_dict(self.profile_fixture["profile"])
        settings = AdminSettingsSnapshotReference.from_dict(self.profile_fixture["admin_settings"])
        before = build_effective_rule_set(
            profile,
            RuleSetPhase.PRE_DEPLOY,
            settings,
            rules,
        )
        approved = rules.approved_snapshot("GLOBAL-S3-PAB-001", 1)
        rules.deprecate(
            "GLOBAL-S3-PAB-001",
            1,
            deprecated_by="contract-reviewer",
            deprecated_at="2026-08-26T04:00:00Z",
            reason="contract reproduction test",
        )
        reproduced = reproduce_effective_rule_set(
            profile,
            RuleSetPhase.PRE_DEPLOY,
            settings,
            rules,
        )
        self.assertEqual(reproduced, before)
        self.assertEqual(
            sources.versions_of("cloud-infra-security-checklist"), ("2026.08", "2026.09")
        )
        self.assertEqual(
            rule_content_hash(rules.get("GLOBAL-S3-PAB-001", 1)),
            approved.approval.rule_content_hash,
        )

    def test_coverage_fixture_does_not_overstate_area_c_or_d_support(self):
        coverage = json.loads(
            (REPO / "fixtures" / "rules" / "governance-coverage.json").read_text(encoding="utf-8")
        )
        self.assertTrue(coverage["reporting_terms_only"])
        global_scope = coverage["global_source_scope"]
        self.assertEqual(
            global_scope["official_snapshot_frozen_source_ids"],
            ["aws-fsbp-1-0-0"],
        )
        self.assertEqual(global_scope["scored_global_source_complete_ids"], [])
        self.assertEqual(global_scope["mapping_view_complete_source_ids"], [])
        defined = {
            identity
            for resource in coverage["resources"]
            for identity in resource["defined_rule_ids"]
        }
        fixture_rules = {
            f"{item['rule_id']}@{item['version']}" for item in self.rule_fixture["rules"]
        }
        self.assertEqual(defined, fixture_rules)
        for resource in coverage["resources"]:
            self.assertLessEqual(
                set(resource["governance_ready_rule_ids"]),
                set(resource["defined_rule_ids"]),
            )
            self.assertEqual(resource["assessment_executable_rule_ids"], [])
            self.assertEqual(resource["remediation_deployable_rule_ids"], [])


if __name__ == "__main__":
    unittest.main()
