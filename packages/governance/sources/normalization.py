"""문서 형식과 무관한 정규화·해시·anchor 규칙.

Loader와 Segmentation이 같은 규칙을 써야 같은 원문이 항상 같은 ``content_hash``를
만든다. 이 규칙이 형식별로 갈라지면 Source별 Score 비교가 성립하지 않으므로
한 모듈에만 둔다.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata


def normalize_for_hash(raw_block: str) -> str:
    """content_hash 대상 정규화.

    문자를 치환하지 않는다. 원문에 충실해야 Evidence로 쓸 수 있기 때문이다.
    줄바꿈 표기와 줄 끝 공백만 정리한다. 이것을 하지 않으면 같은 문서가
    Windows(CRLF)와 Linux(LF)에서 다른 해시를 갖는다.
    """
    text = unicodedata.normalize("NFC", raw_block)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip("\n")


def content_hash(raw_block: str) -> str:
    digest = hashlib.sha256(normalize_for_hash(raw_block).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def bytes_hash(payload: bytes) -> str:
    """업로드 원본 바이트의 해시. 추출 결과가 아니라 파일 자체의 정체성이다."""
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def slugify(value: str) -> str:
    """Heading을 안정적인 anchor 조각으로 바꾼다. 한글 등 비ASCII는 보존한다."""
    text = unicodedata.normalize("NFC", value).strip().casefold()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^\w\-.]", "", text, flags=re.UNICODE)
    return re.sub(r"-{2,}", "-", text).strip("-.")
