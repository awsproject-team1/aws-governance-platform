"""업로드한 임의 문서를 Policy Q&A에서 실제로 쓸 수 있는지 검증한다.

FrozenDocument.sections -> Knowledge Index -> document_id/version 범위 검색
-> PolicyEvidence -> 원문 locator까지 이어지는 경로다.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

from packages.contracts.governance import (
    ContractValidationError,
    Control,
    EvidenceResultStatus,
    PolicyEvidence,
    SourceControlMapping,
    SourceType,
)
from packages.governance.controls.registry import ControlRegistry
from packages.governance.errors import GovernanceConflictError
from packages.governance.mappings.registry import SourceControlMappingRegistry
from packages.governance.sources.index import FrozenDocumentIndex
from packages.governance.sources.ingestion import PolicyDocument, ingest_document
from packages.governance.sources.registry import PolicySourceRegistry
from packages.governance.sources.segmentation import CanonicalHeadingProfile

REPO = Path(__file__).resolve().parents[2]
POLICY_DOC = REPO / "fixtures" / "policy" / "arbitrary-internal-policy.md"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


POLICY_TOOL = load_module("policy_knowledge_port", REPO / "tools" / "policy-knowledge" / "port.py")

ENCRYPTION_SECTION = "데이터-보호-운영-지침/제1장-저장소-운영/1-나.-저장-시-암호화"


def freeze(document_id="acme-data-protection-guideline", version="2026.08", raw_text=None):
    return ingest_document(
        PolicyDocument(
            document_id=document_id,
            document_version=version,
            document_type="md",
            source_type=SourceType.CUSTOMER,
            raw_text=raw_text if raw_text is not None else POLICY_DOC.read_text(encoding="utf-8"),
        ),
        CanonicalHeadingProfile(),
    )


def empty_mappings():
    return SourceControlMappingRegistry(ControlRegistry([]), PolicySourceRegistry([]))


class FrozenDocumentIndexTests(unittest.TestCase):
    def setUp(self):
        self.frozen = freeze()
        self.index = FrozenDocumentIndex([self.frozen])

    def test_search_returns_contract_valid_evidence_with_the_original_locator(self):
        results = self.index.search("저장 시 암호화", [self.frozen.document_id])
        self.assertTrue(results)
        evidence = PolicyEvidence.from_dict(results[0])
        self.assertEqual(evidence.source_reference.section, ENCRYPTION_SECTION)
        self.assertEqual(
            evidence.source_reference.content_hash,
            self.frozen.section_for(ENCRYPTION_SECTION).content_hash,
        )
        self.assertTrue(evidence.locator.startswith("md:line="))
        self.assertIn("암호화", evidence.excerpt)

    def test_excerpt_is_taken_verbatim_from_the_frozen_block(self):
        results = self.index.search("암호화", [self.frozen.document_id])
        block = self.frozen.section_for(ENCRYPTION_SECTION).raw_block
        self.assertIn(PolicyEvidence.from_dict(results[0]).excerpt, block)

    def test_search_is_scoped_to_allowed_sources(self):
        other = freeze(document_id="other-guideline")
        index = FrozenDocumentIndex([self.frozen, other])
        results = index.search("암호화", [other.document_id])
        self.assertTrue(results)
        self.assertEqual(
            {item["source_reference"]["document_id"] for item in results}, {other.document_id}
        )

    def test_search_is_deterministic(self):
        first = self.index.search("버킷 암호화", [self.frozen.document_id])
        second = self.index.search("버킷 암호화", [self.frozen.document_id])
        self.assertEqual(first, second)

    def test_versions_are_indexed_separately(self):
        revised = freeze(
            version="2026.09",
            raw_text=POLICY_DOC.read_text(encoding="utf-8").replace(
                "전체 대역 허용은 금지한다.", "전체 대역 허용은 승인 시 허용한다."
            ),
        )
        index = FrozenDocumentIndex([self.frozen, revised])
        self.assertEqual(index.versions_of(self.frozen.document_id), ("2026.08", "2026.09"))
        results = index.search("전체 대역", [self.frozen.document_id])
        self.assertEqual(
            {item["source_reference"]["document_version"] for item in results},
            {"2026.08", "2026.09"},
        )
        for item in results:
            self.assertTrue(index.verifies(PolicyEvidence.from_dict(item).source_reference))

    def test_same_version_with_different_content_is_rejected(self):
        revised = freeze(
            raw_text=POLICY_DOC.read_text(encoding="utf-8").replace(
                "전체 대역 허용은 금지한다.", "전체 대역 허용은 승인 시 허용한다."
            )
        )
        with self.assertRaises(GovernanceConflictError):
            FrozenDocumentIndex([self.frozen, revised])


class PolicyKnowledgeServiceTests(unittest.TestCase):
    def setUp(self):
        self.frozen = freeze()
        self.index = FrozenDocumentIndex([self.frozen])
        self.adapter = POLICY_TOOL.FrozenDocumentKnowledgeAdapter(self.index)

    def test_uploaded_document_answers_before_any_control_mapping_exists(self):
        """Rule로 승격되기 전에도 업로드 문서로 Q&A가 가능해야 한다."""
        service = POLICY_TOOL.PolicyKnowledgeService(
            self.adapter, empty_mappings(), documents=self.index
        )
        result = service.query("저장 시 암호화", [self.frozen.document_id])
        self.assertIs(result.status, EvidenceResultStatus.FOUND)
        self.assertEqual(result.evidence[0].source_reference.section, ENCRYPTION_SECTION)

    def test_without_the_frozen_index_unmapped_references_are_still_rejected(self):
        service = POLICY_TOOL.PolicyKnowledgeService(self.adapter, empty_mappings())
        with self.assertRaises(ContractValidationError):
            service.query("저장 시 암호화", [self.frozen.document_id])

    def test_control_mapped_reference_still_passes_without_the_index(self):
        sources = PolicySourceRegistry([self.frozen.policy_source])
        controls = ControlRegistry([Control(control_key="s3.encryption.at_rest")])
        mappings = SourceControlMappingRegistry(controls, sources)
        mappings.add(
            SourceControlMapping(
                source_reference=self.frozen.reference_for(ENCRYPTION_SECTION),
                resource_type="aws_s3_bucket",
                control_key="s3.encryption.at_rest",
            )
        )
        # Mapping만으로 통과하는 경로이므로 Mapping된 항목 하나로 좁혀서 확인한다.
        adapter = POLICY_TOOL.FrozenDocumentKnowledgeAdapter(self.index, limit=1)
        service = POLICY_TOOL.PolicyKnowledgeService(adapter, mappings)
        result = service.query("저장 시 암호화", [self.frozen.document_id])
        self.assertIs(result.status, EvidenceResultStatus.FOUND)
        self.assertEqual(result.evidence[0].source_reference.section, ENCRYPTION_SECTION)

    def test_evidence_that_does_not_match_the_frozen_content_is_rejected(self):
        """Adapter가 만들어낸 section/hash를 그대로 Evidence로 쓰지 않는다."""

        class TamperingAdapter:
            def __init__(self, index):
                self._index = index

            def search(self, query, allowed_source_ids):
                for item in self._index.search(query, allowed_source_ids):
                    tampered = {key: value for key, value in item.items()}
                    tampered["source_reference"] = {
                        **item["source_reference"],
                        "content_hash": "sha256:" + "a" * 64,
                    }
                    yield tampered

        service = POLICY_TOOL.PolicyKnowledgeService(
            TamperingAdapter(self.index), empty_mappings(), documents=self.index
        )
        with self.assertRaises(ContractValidationError):
            service.query("저장 시 암호화", [self.frozen.document_id])

    def test_evidence_outside_the_allowed_sources_is_rejected(self):
        other = freeze(document_id="other-guideline")
        index = FrozenDocumentIndex([self.frozen, other])

        class LeakingAdapter:
            """허용 범위를 무시하고 다른 Source의 근거를 돌려주는 Adapter."""

            def __init__(self, index, source_id):
                self._index = index
                self._source_id = source_id

            def search(self, query, allowed_source_ids):
                return self._index.search(query, [self._source_id])

        service = POLICY_TOOL.PolicyKnowledgeService(
            LeakingAdapter(index, other.document_id), empty_mappings(), documents=index
        )
        with self.assertRaises(ContractValidationError):
            service.query("암호화", [self.frozen.document_id])

    def test_no_match_is_not_found_rather_than_an_error(self):
        service = POLICY_TOOL.PolicyKnowledgeService(
            self.adapter, empty_mappings(), documents=self.index
        )
        result = service.query("존재하지않는키워드", [self.frozen.document_id])
        self.assertIs(result.status, EvidenceResultStatus.NOT_FOUND)
        self.assertEqual(result.evidence, ())


if __name__ == "__main__":
    unittest.main()
