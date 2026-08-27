import json
import unittest
from dataclasses import asdict
from pathlib import Path

from packages.contracts.governance import (
    ContractValidationError,
    EvaluationType,
    Rule,
    SourceType,
)
from packages.governance.compliance.readiness import (
    ComplianceItemMapping,
    EvidenceReadinessStatus,
    build_compliance_readiness,
)
from packages.governance.errors import GovernanceConflictError, GovernanceValidationError
from packages.governance.profiles.source_selection import select_global_profile_sources
from packages.governance.sources.catalog import (
    ExcludedControl,
    FrozenGlobalSourceSnapshot,
    GlobalSourceCatalog,
    GlobalSourceDefinition,
    GlobalSourceRole,
    GlobalSourceSnapshotRegistry,
    SourceResultKind,
)
from packages.governance.sources.ingestion import PolicyDocument, ingest_document
from packages.governance.sources.official_snapshot import (
    FrozenOfficialControlSet,
    revalidate_rule_against_official_snapshot,
)
from packages.governance.sources.segmentation import CanonicalHeadingProfile

REPO = Path(__file__).resolve().parents[2]
CATALOG_FIXTURE = REPO / "fixtures" / "policy" / "global-source-catalog.json"
ISMS_FIXTURE = REPO / "fixtures" / "policy" / "isms-readiness-golden.json"
FSBP_S3_FIXTURE = REPO / "fixtures" / "policy" / "aws-fsbp-s3-official-snapshot.json"
RULE_FIXTURE = REPO / "fixtures" / "rules" / "governance-golden.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_catalog() -> GlobalSourceCatalog:
    fixture = load_json(CATALOG_FIXTURE)
    return GlobalSourceCatalog(
        GlobalSourceDefinition.from_dict(item) for item in fixture["definitions"]
    )


class GlobalSourceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.fixture = load_json(CATALOG_FIXTURE)
        self.catalog = build_catalog()

    def test_verified_definitions_do_not_claim_to_be_frozen_snapshots(self):
        self.assertTrue(self.fixture["not_a_frozen_snapshot"])
        self.assertEqual(len(self.catalog.list()), 5)
        self.assertEqual(
            [item.source_id for item in self.catalog.default_profile_candidates()],
            ["aws-fsbp-1-0-0"],
        )

    def test_cis_publisher_and_aws_delivery_reference_remain_distinct(self):
        cis = self.catalog.get("cis-aws-foundations-5-0-0")
        self.assertEqual(cis.publisher, "CIS")
        self.assertEqual(cis.framework_version, "5.0.0")
        self.assertIn("docs.aws.amazon.com", cis.delivery_or_mapping_reference)

    def test_tagging_global_scope_does_not_invent_customer_tag_policy(self):
        tagging = self.catalog.get("aws-resource-tagging-1-0-0")
        self.assertIs(tagging.role, GlobalSourceRole.GOVERNANCE_HYGIENE)
        self.assertIn("필수 Tag Key", tagging.customer_defined_scope)
        self.assertFalse(
            any(
                key in " ".join(tagging.global_evaluation_scope)
                for key in ("Owner", "CostCenter", "Project")
            )
        )

    def test_control_tower_is_conditional_and_never_default(self):
        source_id = "aws-control-tower-controls"
        missing = self.catalog.applicability(source_id, {"AWS_ORGANIZATIONS"})
        self.assertFalse(missing.applicable)
        self.assertIn("AWS_CONTROL_TOWER", missing.missing_capabilities)
        complete = self.catalog.applicability(
            source_id,
            {
                "AWS_ORGANIZATIONS",
                "AWS_CONTROL_TOWER",
                "LANDING_ZONE_AND_OU_CONTEXT",
                "AWS_CONFIG",
                "AWS_SECURITY_HUB",
            },
        )
        self.assertTrue(complete.applicable)
        self.assertFalse(self.catalog.get(source_id).default_profile_eligible)

    def test_isms_p_is_mapping_readiness_not_a_scored_profile(self):
        isms = self.catalog.get("isms-p-2023-11-23")
        self.assertIs(isms.role, GlobalSourceRole.MAPPING_EVIDENCE)
        self.assertIs(isms.result_kind, SourceResultKind.MAPPING_AND_EVIDENCE_READINESS)
        self.assertIsNone(isms.score_label)
        self.assertFalse(isms.default_profile_eligible)
        with self.assertRaisesRegex(GovernanceValidationError, "cannot enter"):
            select_global_profile_sources(self.catalog, (isms.source_id,))

    def test_foundational_sources_stay_independent_in_one_profile_composition(self):
        selected = select_global_profile_sources(
            self.catalog,
            ("aws-fsbp-1-0-0", "cis-aws-foundations-5-0-0"),
        )
        self.assertEqual(
            {item.source_id for item in selected},
            {"aws-fsbp-1-0-0", "cis-aws-foundations-5-0-0"},
        )

    def test_official_or_compliance_score_labels_are_rejected(self):
        value = dict(self.fixture["definitions"][0])
        value["score_label"] = "공식 FSBP Score"
        with self.assertRaisesRegex(ContractValidationError, "official or compliance"):
            GlobalSourceDefinition.from_dict(value)


class GlobalSourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.catalog = build_catalog()
        self.registry = GlobalSourceSnapshotRegistry(self.catalog)

    @staticmethod
    def snapshot(version: str, controls: tuple[str, ...], mapping_version: str = "1"):
        return FrozenGlobalSourceSnapshot.create(
            source_id="aws-fsbp-1-0-0",
            source_version=version,
            framework_version="1.0.0",
            snapshot_date=version,
            collected_at=f"{version}T00:00:00Z",
            official_reference_url=(
                "https://docs.aws.amazon.com/securityhub/latest/userguide/fsbp-standard.html"
            ),
            canonical_content_hash="sha256:" + "a" * 64,
            selected_control_ids=controls,
            excluded_controls=(ExcludedControl("S3.9", "not approved for this Rule Pack"),),
            mapping_version=mapping_version,
        )

    def test_control_set_hash_and_versions_are_immutable(self):
        first = self.snapshot("2026-08-25", ("S3.8",))
        second = self.snapshot("2026-08-26", ("S3.8", "S3.10"), "2")
        self.registry.freeze(first)
        self.registry.freeze(second)
        self.assertNotEqual(first.control_set_hash, second.control_set_hash)
        change = self.registry.compare(first, second)
        self.assertEqual(change.added_control_ids, ("S3.10",))
        self.assertEqual(change.removed_control_ids, ())
        self.assertTrue(change.mapping_changed)
        with self.assertRaises(GovernanceConflictError):
            self.registry.freeze(first)

    def test_reference_definition_alone_cannot_be_frozen_without_controls(self):
        with self.assertRaisesRegex(ContractValidationError, "selected controls"):
            self.snapshot("2026-08-26", ())

    def test_normal_snapshot_path_derives_identity_and_hash_from_frozen_document(self):
        document = ingest_document(
            PolicyDocument(
                document_id="aws-fsbp-1-0-0",
                document_version="fixture-2026-08-26",
                document_type="md",
                source_type=SourceType.GLOBAL,
                raw_text="# FSBP fixture\n\n## S3.8\n\nBlock Public Access fixture text.",
            ),
            CanonicalHeadingProfile(),
        )
        snapshot = FrozenGlobalSourceSnapshot.from_frozen_document(
            document,
            self.catalog.get("aws-fsbp-1-0-0"),
            snapshot_date="2026-08-26",
            collected_at="2026-08-26T00:00:00Z",
            selected_control_ids=("S3.8",),
            excluded_controls=(),
            mapping_version="fixture-1",
        )
        self.assertEqual(snapshot.identity, (document.document_id, document.document_version))
        self.assertRegex(snapshot.canonical_content_hash, r"^sha256:[0-9a-f]{64}$")
        self.assertNotEqual(snapshot.canonical_content_hash, document.source_hash)


class OfficialFsbpS3SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.catalog = build_catalog()
        self.fixture = load_json(FSBP_S3_FIXTURE)
        self.control_set = FrozenOfficialControlSet.from_dict(
            self.fixture,
            self.catalog.get("aws-fsbp-1-0-0"),
        )

    def test_observed_s3_set_is_frozen_and_exactly_partitioned(self):
        self.assertEqual(
            self.control_set.observed_control_ids,
            (
                "S3.1",
                "S3.12",
                "S3.13",
                "S3.19",
                "S3.2",
                "S3.24",
                "S3.25",
                "S3.3",
                "S3.5",
                "S3.6",
                "S3.8",
                "S3.9",
            ),
        )
        self.assertEqual(self.control_set.source_snapshot.selected_control_ids, ("S3.8",))
        self.assertEqual(len(self.control_set.source_snapshot.excluded_controls), 11)
        self.assertRegex(
            self.control_set.source_snapshot.control_set_hash,
            r"^sha256:[0-9a-f]{64}$",
        )

    def test_s3_8_evidence_hash_and_required_observations_are_server_verified(self):
        evidence = self.control_set.evidence_for("S3.8")
        self.assertEqual(evidence.severity.value, "HIGH")
        self.assertEqual(evidence.evaluation_type.value, "AWS")
        self.assertEqual(evidence.official_resource_type, "AWS::S3::Bucket")
        self.assertEqual(
            set(evidence.required_observations),
            {
                "ignorePublicAcls",
                "blockPublicPolicy",
                "blockPublicAcls",
                "restrictPublicBuckets",
            },
        )

        tampered = load_json(FSBP_S3_FIXTURE)
        tampered["selected_control_evidence"][0]["requirement"] = "forged requirement"
        with self.assertRaisesRegex(ContractValidationError, "content_hash mismatch"):
            FrozenOfficialControlSet.from_dict(
                tampered,
                self.catalog.get("aws-fsbp-1-0-0"),
            )

    def test_selected_and_excluded_controls_must_cover_the_observed_set(self):
        tampered = load_json(FSBP_S3_FIXTURE)
        tampered["observed_control_ids"].append("S3.999")
        with self.assertRaisesRegex(ContractValidationError, "exactly partition"):
            FrozenOfficialControlSet.from_dict(
                tampered,
                self.catalog.get("aws-fsbp-1-0-0"),
            )

    def test_existing_active_rule_requires_new_version_and_human_reapproval(self):
        rule_fixture = load_json(RULE_FIXTURE)
        rule = Rule.from_dict(
            next(
                item
                for item in rule_fixture["rules"]
                if item["rule_id"] == "GLOBAL-S3-PAB-001" and item["version"] == 1
            )
        )
        result = revalidate_rule_against_official_snapshot(rule, self.control_set, "S3.8")

        # 승인된 Reference가 새 공식 snapshot에서 파생된 reference와 다르다.
        self.assertFalse(result.source_reference_matches)

        # 의미 필드도 다르다. 공식 S3.8은 AWS 실제 상태로 평가하는 control이지만
        # ADR-0002가 첫 Slice를 고객 IaC 평가로 고정했으므로 Platform Rule은 IAC다.
        # 이 차이는 drift가 아니라 의도된 결정이며 Human Approval이 확인할 항목이다.
        evidence = self.control_set.evidence_for("S3.8")
        self.assertIs(evidence.evaluation_type, EvaluationType.AWS)
        self.assertIs(rule.evaluation_type, EvaluationType.IAC)
        self.assertFalse(result.semantic_fields_match)

        # 나머지 의미 필드는 공식 metadata와 일치한다.
        self.assertEqual(rule.resource_type, evidence.contract_resource_type)
        self.assertIs(rule.severity, evidence.severity)
        self.assertEqual(rule.requirement, evidence.requirement)

        # 두 차이 모두 자동 보정 대상이 아니다. Rule은 그대로 남고 재승인이 필요하다.
        self.assertTrue(result.requires_new_rule_version_and_human_approval)
        self.assertEqual(rule.version, 1)
        self.assertEqual(rule.status.value, "ACTIVE")
        self.assertEqual(
            result.current_source_reference.document_version,
            "1.0.0+2026-08-26.s3-v1",
        )


class IsmsReadinessTests(unittest.TestCase):
    def test_mapping_coverage_and_evidence_distribution_match_fixture(self):
        fixture = load_json(ISMS_FIXTURE)
        self.assertFalse(fixture["authoritative_mapping"])
        items = tuple(ComplianceItemMapping.from_dict(item) for item in fixture["items"])
        summary = build_compliance_readiness(
            source_id=fixture["source_id"],
            source_version=fixture["source_version"],
            selected_item_ids=fixture["selected_item_ids"],
            mappings=items,
        )
        expected = fixture["expected"]
        self.assertEqual(summary.selected_item_count, expected["selected_item_count"])
        self.assertEqual(summary.mapped_item_count, expected["mapped_item_count"])
        self.assertEqual(summary.mapping_coverage, expected["mapping_coverage"])
        self.assertEqual(summary.evidence_status_counts, expected["evidence_status_counts"])
        keys = set(asdict(summary))
        self.assertTrue(keys.isdisjoint(expected["must_not_contain_fields"]))
        self.assertIn("준수율", summary.interpretation)

    def test_manual_and_out_of_scope_items_do_not_become_pass_or_fail(self):
        fixture = load_json(ISMS_FIXTURE)
        items = [ComplianceItemMapping.from_dict(item) for item in fixture["items"]]
        statuses = {item.item_id: item.evidence_status for item in items}
        self.assertIs(statuses["2.5.1"], EvidenceReadinessStatus.MANUAL_REVIEW)
        self.assertIs(statuses["1.4.3"], EvidenceReadinessStatus.OUT_OF_SCOPE)
        self.assertTrue(
            next(item for item in items if item.item_id == "2.5.1").manual_review_required
        )


if __name__ == "__main__":
    unittest.main()
