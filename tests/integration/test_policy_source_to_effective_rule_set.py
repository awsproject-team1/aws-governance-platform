import unittest
from pathlib import Path

from packages.contracts.governance import (
    AdminSettingsSnapshotReference,
    Control,
    PolicyProfile,
    RulePin,
    RuleSetPhase,
    SourceControlMapping,
    SourceType,
)
from packages.governance.controls.registry import ControlRegistry
from packages.governance.mappings.registry import SourceControlMappingRegistry
from packages.governance.profiles.effective import build_effective_rule_set
from packages.governance.profiles.registry import PolicyProfileRegistry
from packages.governance.rules.candidates import RuleCandidateRegistry
from packages.governance.rules.registry import RuleRegistry
from packages.governance.services.rule_candidates import RuleCandidateApplicationService
from packages.governance.sources.ingestion import PolicyDocument, ingest_document
from packages.governance.sources.registry import PolicySourceRegistry
from packages.governance.sources.segmentation import CanonicalHeadingProfile

REPO = Path(__file__).resolve().parents[2]
POLICY = REPO / "fixtures" / "policy" / "arbitrary-internal-policy.md"
ENCRYPTION_SECTION = "데이터-보호-운영-지침/제1장-저장소-운영/1-나.-저장-시-암호화"


class PolicySourceToEffectiveRuleSetIntegrationTests(unittest.TestCase):
    def test_frozen_source_candidate_human_approval_and_profile_handoff(self):
        frozen = ingest_document(
            PolicyDocument(
                document_id="customer-data-protection-policy",
                document_version="2026.08",
                document_type="md",
                source_type=SourceType.CUSTOMER,
                raw_text=POLICY.read_text(encoding="utf-8"),
            ),
            CanonicalHeadingProfile(),
        )
        sources = PolicySourceRegistry([frozen.policy_source])
        controls = ControlRegistry([Control("s3.encryption.at_rest")])
        mappings = SourceControlMappingRegistry(controls, sources)
        mappings.add(
            SourceControlMapping(
                source_reference=frozen.reference_for(ENCRYPTION_SECTION),
                resource_type="aws_s3_bucket",
                control_key="s3.encryption.at_rest",
            )
        )
        candidates = RuleCandidateRegistry()
        rules = RuleRegistry(mappings)
        service = RuleCandidateApplicationService(candidates, rules, mappings)

        result = service.create(
            "candidate-customer-s3-encryption",
            {
                "resource_type": "aws_s3_bucket",
                "control_key": "s3.encryption.at_rest",
                "evaluation_type": "IAC",
                "severity": "MEDIUM",
                "requirement": "고객 정보를 저장하는 버킷은 저장 시 암호화를 적용한다.",
                "remediation_type": "IAC",
            },
            [(frozen, ENCRYPTION_SECTION)],
        )
        self.assertTrue(result.valid)
        snapshot = service.approve(
            "candidate-customer-s3-encryption",
            server_rule_id="CUSTOMER-S3-ENC-010",
            approved_by="authenticated-human-reviewer",
            approved_at="2026-08-26T03:00:00Z",
        )
        self.assertEqual(
            snapshot.rule.source_references[0],
            frozen.reference_for(ENCRYPTION_SECTION),
        )

        profile = PolicyProfile(
            policy_profile_id="customer-governance-profile",
            policy_profile_version=1,
            rule_pins=(RulePin(snapshot.rule.rule_id, snapshot.rule.version),),
        )
        profiles = PolicyProfileRegistry(rules)
        profiles.add(profile)
        effective = build_effective_rule_set(
            profiles.get(*profile.identity),
            RuleSetPhase.INITIAL,
            AdminSettingsSnapshotReference("sha256:" + "a" * 64),
            rules,
        )

        self.assertEqual(effective.rules, (snapshot.rule,))
        self.assertEqual(effective.policy_profile_version, 1)
        self.assertEqual(
            result.candidate.evidence[0].source_reference,
            effective.rules[0].source_references[0],
        )


if __name__ == "__main__":
    unittest.main()
