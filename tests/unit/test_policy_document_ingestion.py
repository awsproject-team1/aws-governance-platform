"""임의 사내 문서 Ingestion이 특정 문서 서식에 종속되지 않는지 검증한다."""

import unittest
from pathlib import Path

from packages.contracts.governance import (
    Control,
    SourceControlMapping,
    SourceType,
)
from packages.governance.controls.registry import ControlRegistry
from packages.governance.errors import GovernanceConflictError, GovernanceValidationError
from packages.governance.mappings.registry import SourceControlMappingRegistry
from packages.governance.sources.ingestion import (
    DocumentIdentity,
    PolicyDocument,
    ingest_document,
    ingest_upload,
    reingest_document,
    reingest_upload,
)
from packages.governance.sources.registry import PolicySourceRegistry
from packages.governance.sources.segmentation import (
    CanonicalHeadingProfile,
    ExtractionMethod,
    LlmSegmentationProfile,
    SegmentationNotImplementedError,
    SegmentConfidence,
    UnsupportedDocumentError,
    content_hash,
    normalize_for_hash,
)
from packages.governance.sources.upload import UploadedFile

REPO = Path(__file__).resolve().parents[2]
ARBITRARY_DOC = REPO / "fixtures" / "policy" / "arbitrary-internal-policy.md"


def build_document(raw_text=None, version="2026.08"):
    return PolicyDocument(
        document_id="acme-data-protection-guideline",
        document_version=version,
        document_type="md",
        source_type=SourceType.CUSTOMER,
        raw_text=raw_text if raw_text is not None else ARBITRARY_DOC.read_text(encoding="utf-8"),
    )


class ArbitraryDocumentIngestionTests(unittest.TestCase):
    def test_previously_unseen_document_is_segmented_without_format_specific_code(self):
        frozen = ingest_document(build_document(), CanonicalHeadingProfile())
        anchors = [item.section for item in frozen.sections]

        self.assertEqual(frozen.method, ExtractionMethod.DETERMINISTIC)
        self.assertGreater(len(frozen.sections), 1)
        # 문서 고유의 번호 체계(1-가, 2-가)가 anchor에 그대로 보존된다.
        self.assertIn("데이터-보호-운영-지침/제1장-저장소-운영/1-가.-버킷-공개-설정", anchors)
        self.assertIn("데이터-보호-운영-지침/제2장-네트워크/2-가.-인바운드-허용-범위", anchors)

    def test_raw_block_is_preserved_not_summarised(self):
        frozen = ingest_document(build_document(), CanonicalHeadingProfile())
        section = frozen.reference_for(
            "데이터-보호-운영-지침/제1장-저장소-운영/1-나.-저장-시-암호화"
        )
        block = next(item.raw_block for item in frozen.sections if item.section == section.section)
        self.assertIn("고객 정보를 저장하는 버킷은 저장 시 암호화를 적용한다.", block)
        self.assertEqual(content_hash(block), section.content_hash)

    def test_generated_references_satisfy_the_registry_contract(self):
        """생성된 Reference가 손으로 쓴 Fixture 없이 Registry 검증을 통과해야 한다."""
        frozen = ingest_document(build_document(), CanonicalHeadingProfile())
        sources = PolicySourceRegistry([frozen.policy_source])
        controls = ControlRegistry([Control(control_key="s3.encryption.at_rest")])
        mappings = SourceControlMappingRegistry(controls, sources)

        reference = frozen.reference_for(
            "데이터-보호-운영-지침/제1장-저장소-운영/1-나.-저장-시-암호화"
        )
        mappings.add(
            SourceControlMapping(
                source_reference=reference,
                resource_type="aws_s3_bucket",
                control_key="s3.encryption.at_rest",
            )
        )
        mappings.require(reference, "aws_s3_bucket", "s3.encryption.at_rest")
        self.assertTrue(mappings.allows_reference(reference))
        self.assertIs(mappings.source_type(reference), SourceType.CUSTOMER)


class FreezingTests(unittest.TestCase):
    def test_reingesting_identical_content_is_stable(self):
        profile = CanonicalHeadingProfile()
        frozen = ingest_document(build_document(), profile)
        again = reingest_document(frozen, build_document(), profile)
        self.assertEqual(again.snapshot_hash, frozen.snapshot_hash)
        self.assertEqual(again.source_references(), frozen.source_references())

    def test_line_ending_and_trailing_whitespace_do_not_change_the_hash(self):
        profile = CanonicalHeadingProfile()
        raw = ARBITRARY_DOC.read_text(encoding="utf-8")
        crlf = raw.replace("\n", "\r\n").replace("다.\r\n", "다.   \r\n")
        self.assertEqual(
            ingest_document(build_document(raw), profile).snapshot_hash,
            ingest_document(build_document(crlf), profile).snapshot_hash,
        )

    def test_changed_content_under_the_same_version_is_rejected(self):
        """같은 version의 내용을 덮어쓰면 과거 Finding의 근거가 조용히 달라진다."""
        profile = CanonicalHeadingProfile()
        frozen = ingest_document(build_document(), profile)
        revised = ARBITRARY_DOC.read_text(encoding="utf-8").replace(
            "전체 대역 허용은 금지한다.", "전체 대역 허용은 승인 시 허용한다."
        )
        with self.assertRaises(GovernanceConflictError):
            reingest_document(frozen, build_document(revised), profile)

    def test_revision_under_a_new_version_produces_a_separate_anchor_set(self):
        profile = CanonicalHeadingProfile()
        first = ingest_document(build_document(version="2026.08"), profile)
        revised = ARBITRARY_DOC.read_text(encoding="utf-8").replace(
            "전체 대역 허용은 금지한다.", "전체 대역 허용은 승인 시 허용한다."
        )
        second = ingest_document(build_document(revised, version="2026.09"), profile)

        self.assertNotEqual(first.snapshot_hash, second.snapshot_hash)
        # 과거 version의 Reference는 그대로 남는다.
        self.assertEqual({item.document_version for item in first.source_references()}, {"2026.08"})
        self.assertEqual(
            {item.document_version for item in second.source_references()}, {"2026.09"}
        )


class ProfileBoundaryTests(unittest.TestCase):
    def test_llm_profile_fails_loudly_instead_of_returning_zero_sections(self):
        with self.assertRaises(SegmentationNotImplementedError) as ctx:
            LlmSegmentationProfile().segment("아무 내용", "pdf")
        self.assertIn("Policy Q&A", str(ctx.exception))

    def test_unsupported_document_type_is_rejected(self):
        with self.assertRaises(UnsupportedDocumentError):
            CanonicalHeadingProfile().segment("# 제목", "pdf")

    def test_document_without_headings_is_reported_not_silently_empty(self):
        with self.assertRaises(UnsupportedDocumentError):
            CanonicalHeadingProfile().segment("heading 없는 평문 문단", "md")

    def test_empty_segmentation_is_never_treated_as_success(self):
        with self.assertRaises(GovernanceValidationError):
            ingest_document(build_document("heading 없음"), CanonicalHeadingProfile())

    def test_low_confidence_sections_are_flagged_for_human_review(self):
        """LLM Profile 구현 시 MEDIUM/LOW 항목이 Candidate 전에 걸러지는 경로."""
        frozen = ingest_document(build_document(), CanonicalHeadingProfile())
        self.assertEqual(frozen.sections_requiring_review(), ())
        self.assertTrue(all(i.confidence is SegmentConfidence.HIGH for i in frozen.sections))

    def test_duplicate_headings_get_deterministic_distinct_anchors(self):
        raw = "# 지침\n## 공통\n내용 A\n## 공통\n내용 B\n"
        anchors = [i.section for i in CanonicalHeadingProfile().segment(raw, "md").sections]
        repeated = [i.section for i in CanonicalHeadingProfile().segment(raw, "md").sections]

        self.assertEqual(len(set(anchors)), len(anchors))
        self.assertEqual(anchors, repeated, "같은 원문은 반복 실행해도 같은 anchor를 내야 한다")
        self.assertIn("지침/공통", anchors)
        self.assertIn("지침/공통~2", anchors)


class NormalizationTests(unittest.TestCase):
    def test_normalization_does_not_substitute_characters(self):
        raw = "  요구사항: 공개 접근을 차단한다.  \r\n\r\n"
        self.assertEqual(normalize_for_hash(raw), "  요구사항: 공개 접근을 차단한다.")


class UploadPathTests(unittest.TestCase):
    """업로드 경계를 거친 경로도 같은 동결 규칙을 따르는지 확인한다."""

    def upload(self, raw_text=None, filename="data-protection.md"):
        content = (
            raw_text if raw_text is not None else ARBITRARY_DOC.read_text(encoding="utf-8")
        ).encode("utf-8")
        return UploadedFile(filename=filename, content=content)

    @property
    def identity(self):
        return DocumentIdentity(
            document_id="acme-data-protection-guideline",
            document_version="2026.08",
            source_type=SourceType.CUSTOMER,
        )

    def test_uploaded_file_produces_the_same_frozen_sections_as_the_text_path(self):
        profile = CanonicalHeadingProfile()
        uploaded = ingest_upload(self.upload(), self.identity, profile)
        inline = ingest_document(build_document(), profile)
        self.assertEqual(uploaded.snapshot_hash, inline.snapshot_hash)
        self.assertEqual(uploaded.source_references(), inline.source_references())

    def test_frozen_document_records_the_parser_that_produced_it(self):
        """Parser가 바뀌면 경계가 달라질 수 있으므로 동결 기준에 Parser 정체성을 포함한다."""
        frozen = ingest_upload(self.upload(), self.identity, CanonicalHeadingProfile())
        self.assertEqual(frozen.parser_profile, "markdown-loader")
        self.assertEqual(frozen.parser_version, "1")
        self.assertTrue(frozen.source_hash.startswith("sha256:"))

    def test_missing_malware_scan_is_carried_into_the_frozen_document(self):
        frozen = ingest_upload(self.upload(), self.identity, CanonicalHeadingProfile())
        self.assertTrue(any("악성코드" in item for item in frozen.extraction_warnings))

    def test_changed_content_under_the_same_version_is_rejected_on_the_upload_path(self):
        profile = CanonicalHeadingProfile()
        frozen = ingest_upload(self.upload(), self.identity, profile)
        revised = ARBITRARY_DOC.read_text(encoding="utf-8").replace(
            "전체 대역 허용은 금지한다.", "전체 대역 허용은 승인 시 허용한다."
        )
        with self.assertRaises(GovernanceConflictError):
            reingest_upload(frozen, self.upload(revised), self.identity, profile)

    def test_reupload_of_identical_content_is_stable(self):
        profile = CanonicalHeadingProfile()
        frozen = ingest_upload(self.upload(), self.identity, profile)
        again = reingest_upload(frozen, self.upload(), self.identity, profile)
        self.assertEqual(again.snapshot_hash, frozen.snapshot_hash)


if __name__ == "__main__":
    unittest.main()
