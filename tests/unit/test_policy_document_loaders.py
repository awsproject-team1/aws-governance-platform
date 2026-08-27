"""형식별 Loader가 원본 구조를 언제 보존하고 언제 명시적으로 실패하는지 고정한다."""

import json
import sys
import unittest
from pathlib import Path

from packages.contracts.governance import SourceType
from packages.governance.errors import GovernanceValidationError
from packages.governance.sources.canonical_document import (
    BlockType,
    DocumentFormat,
    DocumentMetadata,
    SourceLocator,
)
from packages.governance.sources.ingestion import (
    DocumentIdentity,
    PolicyDocument,
    ingest_document,
    ingest_upload,
)
from packages.governance.sources.loaders import (
    DocumentLoaderRegistry,
    ExtractionError,
    HtmlLoader,
    MarkdownLoader,
    OcrRequiredError,
    PdfKind,
    PdfTriageLoader,
    UnsupportedFormatError,
    classify_pdf,
    load_text_document,
)
from packages.governance.sources.loaders.html import MAX_DOM_DEPTH
from packages.governance.sources.loaders.office_xml import parse_office_xml
from packages.governance.sources.segmentation import (
    CanonicalHeadingProfile,
    UnsupportedDocumentError,
    XlsxControlMatrixProfile,
)
from packages.governance.sources.upload import UploadedFile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx_fixture import build_docx, golden_docx, paragraph  # noqa: E402
from pdf_fixture import (  # noqa: E402
    blank_pdf,
    encrypted_pdf,
    golden_pdf,
    mixed_pdf,
    object_stream_pdf,
    scanned_pdf,
)
from xlsx_fixture import control_matrix_xlsx  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
POLICY = REPO / "fixtures" / "policy"
GOLDEN = json.loads((POLICY / "canonical-golden.json").read_text(encoding="utf-8"))

PROFILE = CanonicalHeadingProfile()


def html_document(raw_text, document_id="inline-html"):
    return load_text_document(
        raw_text, DocumentFormat.HTML, document_id=document_id, document_version="1"
    )


def block_texts(document, block_type=None):
    return [
        block.text
        for block in document.blocks
        if block_type is None or block.block_type is block_type
    ]


class GoldenFixtureTests(unittest.TestCase):
    """항목 경계, locator, 해시를 Fixture로 동결한다.

    Parser가 바뀌어 경계가 달라지면 여기에서 먼저 깨져야 한다. 조용히 달라지면
    같은 document_version을 참조하던 과거 Finding의 근거가 함께 달라진다.
    """

    def assert_matches_golden(self, frozen, key):
        expected = GOLDEN[key]
        self.assertEqual(frozen.detected_format.value, expected["detected_format"])
        self.assertEqual(f"{frozen.parser_profile}@{frozen.parser_version}", expected["parser"])
        self.assertEqual(f"{frozen.profile_id}@{frozen.profile_version}", expected["profile"])
        self.assertEqual(
            [
                {
                    "section": item.section,
                    "locator": item.locator,
                    "content_hash": item.content_hash,
                    "raw_block": item.raw_block,
                }
                for item in frozen.sections
            ],
            expected["sections"],
        )
        self.assertEqual(frozen.snapshot_hash, expected["snapshot_hash"])

    def test_markdown_golden(self):
        frozen = ingest_document(
            PolicyDocument(
                document_id="acme-data-protection-guideline",
                document_version="2026.08",
                document_type="md",
                source_type=SourceType.CUSTOMER,
                raw_text=(POLICY / "arbitrary-internal-policy.md").read_text(encoding="utf-8"),
            ),
            PROFILE,
        )
        self.assert_matches_golden(frozen, "markdown")

    def test_html_golden(self):
        frozen = ingest_upload(
            UploadedFile(
                filename="wiki-export-policy.html",
                content=(POLICY / "wiki-export-policy.html").read_bytes(),
            ),
            DocumentIdentity("acme-access-control-wiki", "2026.08", SourceType.CUSTOMER),
            PROFILE,
        )
        self.assert_matches_golden(frozen, "html")

    def test_docx_golden(self):
        frozen = ingest_upload(
            UploadedFile(filename="access-regulation.docx", content=golden_docx()),
            DocumentIdentity("acme-access-regulation", "2026.08", SourceType.CUSTOMER),
            PROFILE,
        )
        self.assert_matches_golden(frozen, "docx")

    def test_pdf_golden(self):
        frozen = ingest_upload(
            UploadedFile(filename="access-policy.pdf", content=golden_pdf()),
            DocumentIdentity("acme-access-policy", "2026.08", SourceType.CUSTOMER),
            PROFILE,
        )
        self.assert_matches_golden(frozen, "pdf")

    def test_xlsx_golden(self):
        frozen = ingest_upload(
            UploadedFile(filename="control-matrix.xlsx", content=control_matrix_xlsx()),
            DocumentIdentity("acme-control-matrix", "2026.08", SourceType.CUSTOMER),
            XlsxControlMatrixProfile(),
        )
        self.assert_matches_golden(frozen, "xlsx")


class HtmlLoaderTests(unittest.TestCase):
    def setUp(self):
        self.document = html_document(
            (POLICY / "wiki-export-policy.html").read_text(encoding="utf-8"),
            document_id="acme-access-control-wiki",
        )

    def test_executable_and_external_elements_are_dropped(self):
        body = "\n".join(block_texts(self.document))
        self.assertNotIn("__wikiTelemetry", body)
        self.assertNotIn("theme.css", body)
        self.assertNotIn("embed/dashboard", body)
        self.assertTrue(
            any("script" in item for item in self.document.extraction_warnings),
            self.document.extraction_warnings,
        )

    def test_link_text_is_kept_and_unsafe_href_is_removed(self):
        body = "\n".join(block_texts(self.document))
        self.assertIn("최소 권한 원칙 (https://wiki.example.com/policy/least-privilege)", body)
        self.assertIn("문의: 여기 대신", body)
        self.assertNotIn("javascript:", body)

    def test_nested_list_depth_is_preserved(self):
        items = block_texts(self.document, BlockType.LIST_ITEM)
        self.assertIn("- 공용 계정을 만들지 않는다.", items)
        self.assertIn("  - 예외는 정보보안팀 승인 기록이 있어야 한다.", items)

    def test_merged_table_cells_keep_their_column_position(self):
        table = block_texts(self.document, BlockType.TABLE)[0]
        self.assertEqual(
            table.split("\n"),
            [
                "| 구분 | 정보보안팀 | 서비스팀 |",
                "| 접근 권한 | 정책 수립 | 요청 및 회수 |",
                "|  | 분기 1회 공동 점검 |  |",
            ],
        )

    def test_unclosed_tags_do_not_discard_the_rest_of_the_document(self):
        document = html_document("<h1>지침<p>본문 1<p>본문 2")
        self.assertEqual(len(document.headings()), 1)
        self.assertIn("본문 2", block_texts(document))

    def test_line_endings_do_not_change_the_extraction(self):
        raw = (POLICY / "wiki-export-policy.html").read_text(encoding="utf-8")
        crlf = html_document(raw.replace("\n", "\r\n"), document_id="acme-access-control-wiki")
        self.assertEqual(
            [item.content_hash for item in crlf.blocks],
            [item.content_hash for item in self.document.blocks],
        )

    def test_deeply_nested_markup_is_rejected_instead_of_crashing_the_loader(self):
        """중첩 상한이 없으면 몇 KB짜리 파일 하나가 RecursionError로 워커를 죽인다.

        RecursionError는 LoaderError 계약 밖이라 거부도 경고도 아닌 크래시가 된다.
        업로드는 신뢰 경계 밖 입력이므로 계약 안의 실패로 바뀌어야 한다.
        """
        deep = f"<html><body>{'<div>' * 500}<p>x</p>{'</div>' * 500}</body></html>"
        self.assertLess(len(deep.encode("utf-8")), 8 * 1024)

        with self.assertRaises(ExtractionError) as caught:
            html_document(deep)
        self.assertIn(str(MAX_DOM_DEPTH), str(caught.exception))

    def test_nesting_below_the_limit_is_still_extracted(self):
        """상한이 정상 문서를 자르지 않는지 함께 고정한다."""
        depth = MAX_DOM_DEPTH - 5
        shallow = f"<html><body>{'<div>' * depth}<p>본문</p>{'</div>' * depth}</body></html>"
        self.assertIn("본문", block_texts(html_document(shallow)))

    def test_dom_locator_points_at_the_element(self):
        heading = self.document.headings()[1]
        self.assertEqual(heading.locator.canonical, "html:dom=html[1]>body[1]>div[1]>h2[1]")


class OfficeXmlGuardTests(unittest.TestCase):
    """OOXML part는 신뢰 경계 밖 입력이다. parser 앞에서 무엇을 막는지 고정한다."""

    DTD = '<?xml version="1.0" encoding="{enc}"?><!DOCTYPE r [<!ENTITY x "boom">]><r>&x;</r>'

    def test_dtd_declaration_is_rejected(self):
        payload = self.DTD.format(enc="UTF-8").encode("utf-8")
        with self.assertRaises(ExtractionError) as caught:
            parse_office_xml(payload, "word/document.xml")
        self.assertIn("DTD/Entity", str(caught.exception))

    def test_utf16_cannot_smuggle_a_dtd_past_the_byte_check(self):
        """원시 byte에서 b"<!DOCTYPE"만 찾으면 UTF-16 part가 그대로 통과한다.

        같은 문자열이 byte 수준에서 다르게 보이기 때문이다. 인코딩을 먼저 고정해야
        DTD 거부가 실제 효력을 갖는다.
        """
        for label, encoding in (("BOM 포함", "utf-16"), ("BOM 없음", "utf-16-be")):
            with self.subTest(label):
                payload = self.DTD.format(enc="UTF-16").encode(encoding)
                self.assertNotIn(b"<!DOCTYPE", payload)  # byte 검사는 놓친다
                with self.assertRaises(ExtractionError) as caught:
                    parse_office_xml(payload, "word/document.xml")
                self.assertIn("UTF-8", str(caught.exception))

    def test_declared_non_utf8_encoding_is_rejected(self):
        payload = '<?xml version="1.0" encoding="ISO-8859-1"?><r>x</r>'.encode("latin-1")
        with self.assertRaises(ExtractionError):
            parse_office_xml(payload, "word/document.xml")

    def test_plain_utf8_part_still_parses(self):
        root = parse_office_xml(b'<?xml version="1.0" encoding="UTF-8"?><r>ok</r>', "part.xml")
        self.assertEqual(root.text, "ok")


class DocxLoaderTests(unittest.TestCase):
    def setUp(self):
        self.document = ingest_upload(
            UploadedFile(filename="regulation.docx", content=golden_docx()),
            DocumentIdentity("acme-access-regulation", "2026.08", SourceType.CUSTOMER),
            PROFILE,
        )

    def test_headings_come_from_style_names_and_outline_levels(self):
        anchors = [item.section for item in self.document.sections]
        self.assertEqual(anchors[0], "접근-통제-규정")
        self.assertIn("접근-통제-규정/제1조-계정-관리", anchors)
        # outlineLvl만 있는 문단도 제목으로 인식한다.
        self.assertIn("접근-통제-규정/제2조-권한-검토", anchors)
        # 같은 제목이 반복되면 문서 순서로 구분한다.
        self.assertIn("접근-통제-규정/제1조-계정-관리~2", anchors)

    def test_numbered_list_depth_and_merged_table_are_preserved(self):
        section = self.document.section_for("접근-통제-규정/제1조-계정-관리")
        self.assertIn("- 공용 계정을 사용하지 않는다.", section.raw_block)
        self.assertIn("  - 불가피한 경우 승인 기록을 남긴다.", section.raw_block)

        table = self.document.section_for("접근-통제-규정/제2조-권한-검토").raw_block
        self.assertIn("| 정기 검토 | 분기 1회 | 정보보안팀 |", table)
        self.assertIn("|  | 상시 점검 |  |", table)

    def test_body_locator_is_recorded(self):
        self.assertEqual(self.document.sections[0].locator, "docx:body=1")

    def test_document_without_headings_fails_loudly(self):
        content = build_docx(paragraph("제목 없이 본문만 있는 문서다."))
        with self.assertRaises(UnsupportedDocumentError):
            ingest_upload(
                UploadedFile(filename="plain.docx", content=content),
                DocumentIdentity("plain-doc", "1", SourceType.CUSTOMER),
                PROFILE,
            )


class PdfTriageTests(unittest.TestCase):
    @property
    def metadata(self):
        return DocumentMetadata(
            document_id="pdf-policy",
            document_version="1",
            detected_format=DocumentFormat.PDF,
            source_hash="sha256:" + "0" * 64,
        )

    def test_text_and_scanned_pdfs_are_classified_apart(self):
        self.assertIs(classify_pdf(golden_pdf()), PdfKind.TEXT)
        self.assertIs(classify_pdf(scanned_pdf()), PdfKind.SCANNED)
        self.assertIs(classify_pdf(encrypted_pdf()), PdfKind.ENCRYPTED)
        self.assertIs(classify_pdf(blank_pdf()), PdfKind.UNDETERMINED)

    def test_compressed_objstm_text_layer_is_detected(self):
        self.assertIn(b"/ObjStm", object_stream_pdf())
        self.assertIs(classify_pdf(object_stream_pdf()), PdfKind.TEXT)

    def test_scanned_pdf_is_not_silently_treated_as_an_empty_document(self):
        with self.assertRaises(OcrRequiredError):
            PdfTriageLoader().load(scanned_pdf(), self.metadata)

    def test_text_pdf_preserves_page_and_block_locators(self):
        document = PdfTriageLoader().load(golden_pdf(), self.metadata)
        self.assertEqual(
            [block.locator.canonical for block in document.blocks],
            [
                "pdf:page=1/block=1",
                "pdf:page=1/block=2",
                "pdf:page=1/block=3",
                "pdf:page=1/block=4",
                "pdf:page=2/block=1",
                "pdf:page=2/block=2",
            ],
        )
        self.assertEqual(
            [block.text for block in document.headings()],
            ["Access Control Policy", "Account Management", "Periodic Review"],
        )

    def test_mixed_text_and_image_pdf_requires_ocr_instead_of_partial_extraction(self):
        with self.assertRaises(OcrRequiredError) as ctx:
            PdfTriageLoader().load(mixed_pdf(), self.metadata)
        self.assertIn("2페이지", str(ctx.exception))

    def test_blank_pdf_fails_loudly(self):
        with self.assertRaises(ExtractionError):
            PdfTriageLoader().load(blank_pdf(), self.metadata)

    def test_encrypted_pdf_fails_without_trying_a_password(self):
        with self.assertRaises(ExtractionError) as ctx:
            PdfTriageLoader().load(encrypted_pdf(), self.metadata)
        self.assertIn("암호화", str(ctx.exception))


class XlsxProfileTests(unittest.TestCase):
    @property
    def identity(self):
        return DocumentIdentity("acme-control-matrix", "2026.08", SourceType.CUSTOMER)

    def load(self, content=None):
        return ingest_upload(
            UploadedFile(
                filename="control-matrix.xlsx",
                content=content if content is not None else control_matrix_xlsx(),
            ),
            self.identity,
            XlsxControlMatrixProfile(),
        )

    def test_one_data_row_becomes_one_frozen_item(self):
        frozen = self.load()
        self.assertEqual(
            [item.section for item in frozen.sections],
            ["controls/row-3", "controls/row-4", "controls/row-5", "archive/row-2"],
        )
        self.assertEqual(
            [item.locator for item in frozen.sections],
            [
                "xlsx:sheet=Controls/range=A3:D3",
                "xlsx:sheet=Controls/range=A4:D4",
                "xlsx:sheet=Controls/range=A5:D5",
                "xlsx:sheet=Archive/range=A2:D2",
            ],
        )

    def test_formula_and_cached_value_are_both_preserved_without_execution(self):
        row = self.load().section_for("controls/row-3").raw_block
        self.assertIn('[formula:=UPPER("active"); cached:ACTIVE]', row)

    def test_merged_hidden_and_filter_state_are_reported_without_dropping_rows(self):
        frozen = self.load()
        warnings = "\n".join(frozen.extraction_warnings)
        self.assertIn("병합 범위", warnings)
        self.assertIn("숨김 시트 'Archive'", warnings)
        self.assertIn("숨김 행(4)", warnings)
        self.assertIn("숨김 열 범위", warnings)
        self.assertIn("AutoFilter(A2:D5)", warnings)
        merged_row = frozen.section_for("controls/row-5").raw_block
        self.assertIn(
            "| NET-001 | Ingress is restricted to approved ranges. |  | ACTIVE |", merged_row
        )

    def test_formula_without_cached_value_fails_loudly(self):
        with self.assertRaises(ExtractionError) as ctx:
            self.load(control_matrix_xlsx(formula_cache=None))
        self.assertIn("계산 캐시값", str(ctx.exception))

    def test_general_heading_profile_does_not_absorb_control_matrix(self):
        with self.assertRaises(UnsupportedDocumentError):
            ingest_upload(
                UploadedFile(filename="control-matrix.xlsx", content=control_matrix_xlsx()),
                self.identity,
                CanonicalHeadingProfile(),
            )


class LoaderRegistryTests(unittest.TestCase):
    def test_missing_loader_is_reported_as_unsupported_format(self):
        registry = DocumentLoaderRegistry([MarkdownLoader()])
        metadata = DocumentMetadata(
            document_id="doc",
            document_version="1",
            detected_format=DocumentFormat.HTML,
            source_hash="sha256:" + "0" * 64,
        )
        with self.assertRaises(UnsupportedFormatError):
            registry.load(b"<h1>x</h1>", metadata)

    def test_one_format_cannot_have_two_loaders(self):
        with self.assertRaises(GovernanceValidationError):
            DocumentLoaderRegistry([HtmlLoader(), HtmlLoader()])

    def test_plain_text_without_headings_is_reported_not_silently_empty(self):
        with self.assertRaises(UnsupportedDocumentError):
            PROFILE.segment("제목 없는 평문 문단입니다.", "txt")


class LocatorTests(unittest.TestCase):
    def test_locator_serialises_to_a_stable_string(self):
        locator = SourceLocator.of("xlsx", sheet="Controls").child(range="A3:D3")
        self.assertEqual(locator.canonical, "xlsx:sheet=Controls/range=A3:D3")

    def test_locator_rejects_values_that_break_the_canonical_form(self):
        with self.assertRaises(GovernanceValidationError):
            SourceLocator.of("md", line="1/2")


if __name__ == "__main__":
    unittest.main()
