"""OOXML part를 여는 공용 경계.

DOCX/XLSX는 둘 다 ZIP 안의 XML part를 읽는다. 그 XML은 고객이 업로드한 신뢰 경계 밖
입력이므로 parser에 넘기기 전에 같은 검사를 거쳐야 한다. 검사를 Loader마다 복사해 두면
한쪽만 고치는 사고가 나므로 여기 한 곳에 둔다.

막는 것과 막지 않는 것을 분명히 해 둔다.

- External Entity(XXE)는 여기서 막기 전에 이미 도달 불가능하다. Python의 expat은 정의되지
  않은 entity를 거부하므로 파일 노출이나 SSRF 경로가 열리지 않는다.
- 남는 위험은 내부 entity 확장이다. expat에도 자체 증폭 제한이 있지만 그것은 runtime
  버전에 딸린 성질이고 우리가 보장한 것이 아니다. 그래서 DTD/Entity 선언 자체를 거부한다.
- 그 거부가 실제로 효력을 가지려면 선언을 **읽을 수 있어야** 한다. 원시 byte에서
  ``b"<!DOCTYPE"``만 찾으면 UTF-16으로 인코딩된 part가 그대로 통과한다. 같은 문자열이
  byte 수준에서는 다르게 보이기 때문이다. 그래서 인코딩을 먼저 UTF-8로 고정한 뒤 검사한다.

OOXML 표준 part는 UTF-8이다. 다른 인코딩을 거부해도 정상 문서를 자르지 않는다.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree

from .base import ExtractionError

# XML 선언의 encoding 속성. 선언은 문서 맨 앞에만 올 수 있다.
_XML_DECLARATION = re.compile(rb"^\s*<\?xml[^>]*\?>", re.IGNORECASE)
_DECLARED_ENCODING = re.compile(rb"""encoding\s*=\s*["']([A-Za-z0-9._-]+)["']""", re.IGNORECASE)

# UTF-8로 처리해도 의미가 같은 인코딩만 허용한다.
_ALLOWED_ENCODINGS = frozenset({"utf-8", "utf8", "us-ascii", "ascii"})

# BOM. UTF-16/UTF-32는 byte 수준 검사를 무력화하므로 거부한다.
_REJECTED_BOMS = (
    (b"\xff\xfe\x00\x00", "UTF-32LE"),
    (b"\x00\x00\xfe\xff", "UTF-32BE"),
    (b"\xff\xfe", "UTF-16LE"),
    (b"\xfe\xff", "UTF-16BE"),
)

# BOM 없는 UTF-16은 `<?` 또는 `<` 가 NUL과 섞여 나타난다.
_BOMLESS_UTF16_PREFIXES = (b"<\x00", b"\x00<")

_UTF8_BOM = b"\xef\xbb\xbf"


def _reject_non_utf8_encoding(payload: bytes, part: str) -> None:
    for bom, label in _REJECTED_BOMS:
        if payload.startswith(bom):
            raise ExtractionError(f"UTF-8이 아닌 XML part는 처리하지 않는다: {part} ({label} BOM)")

    body = payload[len(_UTF8_BOM) :] if payload.startswith(_UTF8_BOM) else payload
    if body.startswith(_BOMLESS_UTF16_PREFIXES):
        raise ExtractionError(f"UTF-8이 아닌 XML part는 처리하지 않는다: {part} (UTF-16)")

    declaration = _XML_DECLARATION.match(body)
    if declaration is not None:
        declared = _DECLARED_ENCODING.search(declaration.group(0))
        if declared is not None:
            name = declared.group(1).decode("ascii", "replace").lower()
            if name not in _ALLOWED_ENCODINGS:
                raise ExtractionError(
                    f"UTF-8이 아닌 XML part는 처리하지 않는다: {part} (encoding={name})"
                )


def parse_office_xml(payload: bytes, part: str) -> ElementTree.Element:
    """OOXML part를 DTD/Entity 선언 없이 UTF-8로 확인한 뒤 연다."""
    _reject_non_utf8_encoding(payload, part)

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError(f"XML part가 UTF-8이 아니다: {part}") from exc

    # 인코딩을 고정한 뒤라야 이 검사가 우회되지 않는다.
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise ExtractionError(f"DTD/Entity가 포함된 XML part는 처리하지 않는다: {part}")

    try:
        return ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise ExtractionError(f"XML part를 파싱할 수 없다: {part}") from exc
