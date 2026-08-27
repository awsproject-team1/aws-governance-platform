"""업로드 파일 보안 검사. Loader보다 먼저 실행되는 신뢰 경계다.

업로드된 정책 문서는 신뢰할 수 없는 입력이다. Parser는 어느 것이든 공격 표면이므로
Parser에 바이트를 넘기기 전에 형식과 크기를 확정한다. 여기에서 막는 것:

- 확장자 allowlist 밖의 파일
- 확장자와 실제 signature가 다른 파일
- Macro 포함 Office 문서(docm/xlsm)와 legacy binary(doc/xls)
- 암호화된 문서
- 압축 폭탄(entry 수, 해제 크기, 압축비)과 경로 탈출 entry
- 일반 압축파일
- 잘못된 text 인코딩과 NUL 바이트

여기에서 하지 않는 것:

- ``Content-Type`` 신뢰. 선언값은 metadata로만 보존하고 판정에 쓰지 않는다.
- 업로드 파일명 재사용. 저장 key는 내용 해시로 새로 만든다.
- 악성코드 검사 자체. Scanner는 주입받으며, 없으면 조용히 넘어가지 않고 경고를 남긴다.

Parser 실행 격리(권한 축소된 별도 실행 환경)는 이 모듈이 아니라 배포 경계의 책임이다.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from ..errors import GovernanceValidationError
from .canonical_document import DocumentFormat
from .normalization import bytes_hash

#: 한 파일의 최대 크기. Parser에 넘기기 전에 확정한다.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

#: OOXML 컨테이너 해제 한도. 압축 폭탄 방어.
MAX_ARCHIVE_ENTRIES = 512
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 200

#: 확장자 allowlist. 이 표에 없는 확장자는 거부한다.
ALLOWED_EXTENSIONS: dict[str, DocumentFormat] = {
    "md": DocumentFormat.MARKDOWN,
    "markdown": DocumentFormat.MARKDOWN,
    "txt": DocumentFormat.TXT,
    "html": DocumentFormat.HTML,
    "htm": DocumentFormat.HTML,
    "docx": DocumentFormat.DOCX,
    "xlsx": DocumentFormat.XLSX,
    "pdf": DocumentFormat.PDF,
}

#: 이유를 구분해서 거부하는 확장자. "모르는 형식"과 "알고도 막는 형식"은 다르다.
DENIED_EXTENSIONS: dict[str, tuple[str, str]] = {
    "docm": ("MACRO_ENABLED_FORMAT", "Macro 포함 문서는 MVP에서 받지 않는다"),
    "xlsm": ("MACRO_ENABLED_FORMAT", "Macro 포함 문서는 MVP에서 받지 않는다"),
    "pptm": ("MACRO_ENABLED_FORMAT", "Macro 포함 문서는 MVP에서 받지 않는다"),
    "doc": ("LEGACY_BINARY_FORMAT", "legacy binary Office 문서는 받지 않는다"),
    "xls": ("LEGACY_BINARY_FORMAT", "legacy binary Office 문서는 받지 않는다"),
    "ppt": ("LEGACY_BINARY_FORMAT", "legacy binary Office 문서는 받지 않는다"),
    "rtf": ("LEGACY_BINARY_FORMAT", "RTF는 정책 문서 형식에서 제외한다"),
    "zip": ("ARCHIVE_NOT_ALLOWED", "압축파일은 정책 문서 형식에서 제외한다"),
    "7z": ("ARCHIVE_NOT_ALLOWED", "압축파일은 정책 문서 형식에서 제외한다"),
    "gz": ("ARCHIVE_NOT_ALLOWED", "압축파일은 정책 문서 형식에서 제외한다"),
    "tar": ("ARCHIVE_NOT_ALLOWED", "압축파일은 정책 문서 형식에서 제외한다"),
}

_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_PDF_SIGNATURE = b"%PDF-"
_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_TEXT_FORMATS = (DocumentFormat.MARKDOWN, DocumentFormat.TXT, DocumentFormat.HTML)
_OOXML_FORMATS = (DocumentFormat.DOCX, DocumentFormat.XLSX)
_REQUIRED_OOXML_PART = {
    DocumentFormat.DOCX: "word/document.xml",
    DocumentFormat.XLSX: "xl/workbook.xml",
}


class UploadRejectedError(GovernanceValidationError):
    """업로드를 거부한다. ``reason``은 API/로그에서 안정적으로 쓰는 코드다."""

    code = "UPLOAD_REJECTED"

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(f"{reason}: {message}")
        self.reason = reason


class ScanVerdict(str, Enum):
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    UNAVAILABLE = "UNAVAILABLE"


class MalwareScanner(Protocol):
    def scan(self, payload: bytes) -> ScanVerdict: ...


@dataclass(frozen=True)
class UploadedFile:
    """사용자가 올린 그대로의 파일. 어떤 필드도 신뢰하지 않는다."""

    filename: str
    content: bytes
    declared_content_type: str | None = None


@dataclass(frozen=True)
class ValidatedUpload:
    """보안 검사를 통과한 업로드본. Loader는 이 값만 받는다.

    ``storage_key``는 업로드 파일명을 쓰지 않는다. 사용자가 정한 이름을 저장 경로로
    재사용하면 경로 탈출과 덮어쓰기가 가능해진다.
    """

    storage_key: str
    detected_format: DocumentFormat
    source_hash: str
    size_bytes: int
    display_filename: str
    declared_content_type: str | None
    warnings: tuple[str, ...] = ()


def sanitize_filename(filename: str) -> str:
    """화면 표시에만 쓰는 이름. 저장 경로로는 쓰지 않는다."""
    if not isinstance(filename, str):
        return "upload"
    name = filename.replace("\\", "/").split("/")[-1]
    name = "".join(char for char in name if char.isprintable()).strip()
    name = name.lstrip(".") or "upload"
    return name[:255]


def extension_of(filename: str) -> str:
    name = sanitize_filename(filename)
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[1].casefold()


def decode_utf8(content: bytes) -> str:
    """Text 형식 원문 디코딩. 손실 복구를 하지 않는다."""
    payload = content
    if payload.startswith(b"\xef\xbb\xbf"):
        payload = payload[3:]
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadRejectedError("INVALID_TEXT_ENCODING", "text 문서는 UTF-8이어야 한다") from exc


def _reject_signature_mismatch(detail: str) -> UploadRejectedError:
    return UploadRejectedError("SIGNATURE_MISMATCH", f"확장자와 실제 파일 형식이 다르다: {detail}")


def _inspect_ooxml(content: bytes, declared: DocumentFormat) -> None:
    """OOXML 컨테이너를 열지 않고 검사만 한다. 압축 해제 결과는 Loader가 다룬다."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
        entries = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise UploadRejectedError("MALFORMED_ARCHIVE", "OOXML 컨테이너를 열 수 없다") from exc

    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise UploadRejectedError(
            "ARCHIVE_LIMIT_EXCEEDED", f"entry가 {MAX_ARCHIVE_ENTRIES}개를 넘는다"
        )

    total_uncompressed = 0
    total_compressed = 0
    names = set()
    for entry in entries:
        name = entry.filename
        names.add(name)
        if name.startswith("/") or "\\" in name or ".." in name.split("/"):
            raise UploadRejectedError(
                "ARCHIVE_UNSAFE_ENTRY", f"컨테이너에 안전하지 않은 경로가 있다: {name}"
            )
        if entry.flag_bits & 0x1:
            raise UploadRejectedError("ENCRYPTED_DOCUMENT", "암호화된 entry가 있다")
        total_uncompressed += entry.file_size
        total_compressed += entry.compress_size

    if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise UploadRejectedError("ARCHIVE_LIMIT_EXCEEDED", "해제 크기 한도를 넘는다")
    if total_uncompressed > MAX_ARCHIVE_COMPRESSION_RATIO * max(total_compressed, 1):
        raise UploadRejectedError("ARCHIVE_LIMIT_EXCEEDED", "압축비 한도를 넘는다")

    if any(name.endswith("vbaProject.bin") or name.endswith("vbaData.xml") for name in names):
        raise UploadRejectedError("MACRO_ENABLED_FORMAT", "Macro가 포함된 문서다")
    if any(name.startswith("EncryptedPackage") or name == "EncryptionInfo" for name in names):
        raise UploadRejectedError("ENCRYPTED_DOCUMENT", "암호화된 Office 문서다")
    if "[Content_Types].xml" not in names:
        raise _reject_signature_mismatch("OOXML 필수 part가 없다")

    required = _REQUIRED_OOXML_PART[declared]
    if required not in names:
        other = next(
            (
                fmt
                for fmt in _OOXML_FORMATS
                if fmt is not declared and _REQUIRED_OOXML_PART[fmt] in names
            ),
            None,
        )
        detail = f"{declared.value} 확장자이지만 {other.value} 구조다" if other else "구조 불일치"
        raise _reject_signature_mismatch(detail)


def _inspect_pdf(content: bytes) -> None:
    if not content.startswith(_PDF_SIGNATURE):
        raise _reject_signature_mismatch("PDF signature가 없다")
    if b"/Encrypt" in content:
        raise UploadRejectedError(
            "ENCRYPTED_DOCUMENT", "암호화된 PDF는 추출하지 않고 명시적으로 실패한다"
        )


def _inspect_text(content: bytes) -> None:
    if content.startswith(_ZIP_SIGNATURES) or content.startswith(_PDF_SIGNATURE):
        raise _reject_signature_mismatch("text 확장자이지만 binary 컨테이너다")
    if content.startswith(_OLE_SIGNATURE):
        raise _reject_signature_mismatch("text 확장자이지만 legacy binary 문서다")
    if b"\x00" in content:
        raise UploadRejectedError("INVALID_TEXT_ENCODING", "text 문서에 NUL 바이트가 있다")
    decode_utf8(content)


def validate_upload(
    upload: UploadedFile, *, scanner: MalwareScanner | None = None
) -> ValidatedUpload:
    """업로드를 검사하고 Loader가 받을 수 있는 형태로 확정한다."""
    content = upload.content
    if not isinstance(content, (bytes, bytearray)):
        raise UploadRejectedError("INVALID_PAYLOAD", "업로드 본문은 바이트여야 한다")
    content = bytes(content)
    if not content:
        raise UploadRejectedError("EMPTY_FILE", "빈 파일은 받지 않는다")
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadRejectedError("FILE_TOO_LARGE", f"최대 {MAX_UPLOAD_BYTES} 바이트까지만 받는다")

    extension = extension_of(upload.filename)
    if extension in DENIED_EXTENSIONS:
        reason, message = DENIED_EXTENSIONS[extension]
        raise UploadRejectedError(reason, message)
    detected = ALLOWED_EXTENSIONS.get(extension)
    if detected is None:
        raise UploadRejectedError(
            "EXTENSION_NOT_ALLOWED", f"허용되지 않은 확장자다: {extension or '(없음)'}"
        )

    if detected in _OOXML_FORMATS:
        if content.startswith(_OLE_SIGNATURE):
            raise UploadRejectedError(
                "ENCRYPTED_DOCUMENT", "암호화되었거나 legacy binary인 Office 문서다"
            )
        if not content.startswith(_ZIP_SIGNATURES):
            raise _reject_signature_mismatch("OOXML 컨테이너가 아니다")
        _inspect_ooxml(content, detected)
    elif detected is DocumentFormat.PDF:
        _inspect_pdf(content)
    else:
        _inspect_text(content)

    warnings: list[str] = []
    if scanner is None:
        warnings.append("악성코드 검사를 수행하지 않았다. 운영 배포 전에 Scanner를 연결해야 한다.")
    else:
        verdict = scanner.scan(content)
        if verdict is ScanVerdict.INFECTED:
            raise UploadRejectedError("MALWARE_DETECTED", "악성코드 검사에서 거부됐다")
        if verdict is not ScanVerdict.CLEAN:
            raise UploadRejectedError(
                "SCAN_UNAVAILABLE", "악성코드 검사를 완료하지 못해 업로드를 보류한다"
            )

    declared_type = upload.declared_content_type
    if declared_type and declared_type.strip():
        warnings.append(
            f"선언된 Content-Type({declared_type})은 판정에 쓰지 않고 metadata로만 보존한다."
        )

    source_hash = bytes_hash(content)
    return ValidatedUpload(
        storage_key=f"policy-documents/{source_hash.split(':', 1)[1]}.{detected.value}",
        detected_format=detected,
        source_hash=source_hash,
        size_bytes=len(content),
        display_filename=sanitize_filename(upload.filename),
        declared_content_type=declared_type,
        warnings=tuple(warnings),
    )
