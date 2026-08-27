import json
import unittest
from pathlib import Path

from packages.contracts.governance import (
    AdminSettingsSnapshotReference,
    AssessmentPhase,
    ContractValidationError,
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

    def test_unknown_fields_are_rejected_instead_of_being_discarded(self):
        """조용히 버리면 Consumer의 오타가 오류가 아니라 잘못된 값이 된다.

        `sevirity`가 버려지면 severity는 payload가 우연히 담고 있던 값을 유지한다.
        severity는 scoring 가중치이므로 결과는 아무 오류 없이 잘못된 준수 점수다.
        """
        base = dict(self.rule_fixture["rules"][0])
        for label, extra in (
            ("오타", {"sevirity": "LOW"}),
            ("권한 상승 시도", {"admin_override": True}),
        ):
            with self.subTest(label):
                with self.assertRaises(ContractValidationError) as caught:
                    Rule.from_dict({**base, **extra})
                self.assertIn("unknown field", str(caught.exception))

    def test_remediation_type_shape_is_constrained_without_fixing_the_vocabulary(self):
        """전체 Enum은 Area D와 함께 정할 Open Decision이지만 형식은 지금 고정한다.

        이 값은 승인 semantic hash 안에 있으므로 임의 문자열을 허용하면 승인 binding이
        영구히 흔들린다.
        """
        base = dict(self.rule_fixture["rules"][0])
        for accepted in ("TERRAFORM_PATCH", "MANUAL", "GUIDE"):
            with self.subTest(accepted):
                self.assertEqual(
                    Rule.from_dict({**base, "remediation_type": accepted}).remediation_type,
                    accepted,
                )
        for rejected in ("terraform patch!!", "<script>x</script>", "terraform_patch"):
            with self.subTest(rejected):
                with self.assertRaises(ContractValidationError):
                    Rule.from_dict({**base, "remediation_type": rejected})

    def test_rule_content_hash_does_not_depend_on_source_reference_order(self):
        """근거가 같고 순서만 다른 Rule은 같은 승인 hash를 가져야 한다.

        canonical_json의 sort_keys는 dict key만 정렬하고 배열은 그대로 둔다. 정렬하지
        않으면 재직렬화가 순서를 바꾸는 것만으로 승인 binding이 깨진다.
        """
        base = dict(self.rule_fixture["rules"][0])
        first = base["source_references"][0]
        second = {**first, "section": "9.9-Z", "content_hash": "sha256:" + "b" * 64}
        forward = Rule.from_dict({**base, "source_references": [first, second]})
        reverse = Rule.from_dict({**base, "source_references": [second, first]})
        self.assertEqual(rule_content_hash(forward), rule_content_hash(reverse))

    def test_effective_rule_set_is_stable_structured_input_for_area_c(self):
        profile = PolicyProfile.from_dict(self.profile_fixture["profile"])
        settings = AdminSettingsSnapshotReference.from_dict(self.profile_fixture["admin_settings"])
        effective = build_effective_rule_set(
            profile, RuleSetPhase.PRE_DEPLOY, settings, self.rules
        ).to_dict()
        self.assertEqual(effective["policy_profile_version"], 1)
        self.assertEqual(effective["phase"], "PRE_DEPLOY")
        # 재현 가능한 rule_set_hash가 이 경계의 핵심 보장이므로 형태가 아니라 값을 고정한다.
        # 형태만 검사하면 projection이나 정렬이 바뀌어도 CI가 조용히 통과한다.
        self.assertEqual(
            effective["rule_set_hash"],
            self.profile_fixture["expected_rule_set_hash"]["PRE_DEPLOY"],
        )
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
