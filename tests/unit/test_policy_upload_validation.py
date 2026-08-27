"""업로드 보안 경계. Parser에 바이트가 닿기 전에 무엇을 막는지 고정한다."""

import io
import unittest
import zipfile

from packages.governance.sources.upload import (
    MAX_UPLOAD_BYTES,
    ScanVerdict,
    UploadedFile,
    UploadRejectedError,
    validate_upload,
)

MARKDOWN = "# 지침\n\n내용\n".encode()
OLE_HEADER = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64


def build_zip(entries, *, compression=zipfile.ZIP_DEFLATED):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def minimal_docx(extra=None):
    entries = {
        "[Content_Types].xml": "<Types/>",
        "word/document.xml": "<w:document/>",
    }
    entries.update(extra or {})
    return build_zip(entries)


def reason_of(callable_, *args, **kwargs):
    try:
        callable_(*args, **kwargs)
    except UploadRejectedError as error:
        return error.reason
    raise AssertionError("업로드가 거부되지 않았다")


class AcceptedUploadTests(unittest.TestCase):
    def test_storage_key_is_derived_from_content_not_from_the_uploaded_name(self):
        """사용자가 정한 파일명을 저장 경로로 재사용하면 경로 탈출과 덮어쓰기가 가능해진다."""
        validated = validate_upload(UploadedFile(filename="../../etc/passwd.md", content=MARKDOWN))
        digest = validated.source_hash.split(":", 1)[1]
        self.assertEqual(validated.storage_key, f"policy-documents/{digest}.md")
        self.assertEqual(validated.display_filename, "passwd.md")
        self.assertNotIn("..", validated.storage_key)

    def test_declared_content_type_is_recorded_but_never_decides_the_format(self):
        validated = validate_upload(
            UploadedFile(
                filename="policy.md", content=MARKDOWN, declared_content_type="application/pdf"
            )
        )
        self.assertEqual(validated.detected_format.value, "md")
        self.assertTrue(any("Content-Type" in item for item in validated.warnings))

    def test_missing_malware_scan_is_reported_instead_of_silently_skipped(self):
        validated = validate_upload(UploadedFile(filename="policy.md", content=MARKDOWN))
        self.assertTrue(any("악성코드" in item for item in validated.warnings))

    def test_clean_scan_leaves_no_scanner_warning(self):
        class Scanner:
            def scan(self, payload):
                return ScanVerdict.CLEAN

        validated = validate_upload(
            UploadedFile(filename="policy.md", content=MARKDOWN), scanner=Scanner()
        )
        self.assertFalse(any("악성코드" in item for item in validated.warnings))


class RejectedUploadTests(unittest.TestCase):
    def test_extension_allowlist(self):
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.exe", content=b"MZ")),
            "EXTENSION_NOT_ALLOWED",
        )
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy", content=MARKDOWN)),
            "EXTENSION_NOT_ALLOWED",
        )

    def test_known_dangerous_formats_are_rejected_with_their_own_reason(self):
        """'모르는 형식'과 '알고도 막는 형식'을 같은 오류로 뭉뚱그리지 않는다."""
        cases = {
            "policy.docm": "MACRO_ENABLED_FORMAT",
            "matrix.xlsm": "MACRO_ENABLED_FORMAT",
            "policy.doc": "LEGACY_BINARY_FORMAT",
            "policy.zip": "ARCHIVE_NOT_ALLOWED",
        }
        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                upload = UploadedFile(filename=filename, content=b"PK\x03\x04")
                self.assertEqual(reason_of(validate_upload, upload), expected)

    def test_extension_must_match_the_real_signature(self):
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.md", content=minimal_docx())),
            "SIGNATURE_MISMATCH",
        )
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.docx", content=MARKDOWN)),
            "SIGNATURE_MISMATCH",
        )

    def test_docx_extension_with_xlsx_structure_is_rejected(self):
        content = build_zip({"[Content_Types].xml": "<Types/>", "xl/workbook.xml": "<w/>"})
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.docx", content=content)),
            "SIGNATURE_MISMATCH",
        )

    def test_macro_part_inside_a_docx_container_is_rejected(self):
        content = minimal_docx({"word/vbaProject.bin": "binary"})
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.docx", content=content)),
            "MACRO_ENABLED_FORMAT",
        )

    def test_encrypted_office_documents_are_rejected(self):
        encrypted = build_zip({"[Content_Types].xml": "<Types/>", "EncryptedPackage": "cipher"})
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.docx", content=encrypted)),
            "ENCRYPTED_DOCUMENT",
        )
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.docx", content=OLE_HEADER)),
            "ENCRYPTED_DOCUMENT",
        )

    def test_encrypted_pdf_is_rejected_instead_of_partially_extracted(self):
        content = b"%PDF-1.7\n/Encrypt 12 0 R\ntrailer\n"
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.pdf", content=content)),
            "ENCRYPTED_DOCUMENT",
        )

    def test_archive_limits_stop_compression_bombs(self):
        bomb = minimal_docx({"word/media/big.bin": "A" * 4_000_000})
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.docx", content=bomb)),
            "ARCHIVE_LIMIT_EXCEEDED",
        )

    def test_archive_entry_paths_must_stay_inside_the_container(self):
        content = build_zip(
            {
                "[Content_Types].xml": "<Types/>",
                "word/document.xml": "<w:document/>",
                "../escape.xml": "<x/>",
            }
        )
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.docx", content=content)),
            "ARCHIVE_UNSAFE_ENTRY",
        )

    def test_text_documents_must_be_utf8_without_nul(self):
        invalid = UploadedFile(filename="policy.md", content=b"\xff\xfe\x00#")
        self.assertEqual(reason_of(validate_upload, invalid), "INVALID_TEXT_ENCODING")
        self.assertEqual(
            reason_of(
                validate_upload, UploadedFile(filename="policy.txt", content=b"text\x00text")
            ),
            "INVALID_TEXT_ENCODING",
        )

    def test_empty_and_oversized_uploads(self):
        self.assertEqual(
            reason_of(validate_upload, UploadedFile(filename="policy.md", content=b"")),
            "EMPTY_FILE",
        )
        self.assertEqual(
            reason_of(
                validate_upload,
                UploadedFile(filename="policy.md", content=b"a" * (MAX_UPLOAD_BYTES + 1)),
            ),
            "FILE_TOO_LARGE",
        )

    def test_malware_scan_failure_is_not_treated_as_clean(self):
        class Infected:
            def scan(self, payload):
                return ScanVerdict.INFECTED

        class Unavailable:
            def scan(self, payload):
                return ScanVerdict.UNAVAILABLE

        upload = UploadedFile(filename="policy.md", content=MARKDOWN)
        self.assertEqual(reason_of(validate_upload, upload, scanner=Infected()), "MALWARE_DETECTED")
        self.assertEqual(
            reason_of(validate_upload, upload, scanner=Unavailable()), "SCAN_UNAVAILABLE"
        )


if __name__ == "__main__":
    unittest.main()
