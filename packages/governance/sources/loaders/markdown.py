"""Markdown / 평문 Loader.

heading, 목록, 표, 코드 블록, 인용을 결정론적으로 구분한다. 원문 문자열은 요약하지
않고 그대로 옮기며, 목록의 들여쓰기를 보존해 중첩 구조가 Block 안에 남게 한다.

평문(txt)은 heading이 없으므로 문단만 나온다. 그 경우 Segmentation이 조용히 빈
결과를 내지 않고 "heading이 없다"로 실패한다.
"""

from __future__ import annotations

import re
import unicodedata

from ..canonical_document import (
    BlockType,
    CanonicalDocumentBuilder,
    CanonicalPolicyDocument,
    DocumentFormat,
    DocumentMetadata,
    SourceLocator,
)
from ..upload import decode_utf8
from .base import DocumentLoader

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+\S")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_DELIMITER = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
_QUOTE = re.compile(r"^\s*>")


def split_lines(raw_text: str) -> list[str]:
    """줄 끝 공백과 줄바꿈 표기만 정리한다. 줄 번호는 원본과 같게 유지한다."""
    text = unicodedata.normalize("NFC", raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return [line.rstrip() for line in text.split("\n")]


class MarkdownLoader(DocumentLoader):
    parser_profile = "markdown-loader"
    parser_version = "1"
    supported_formats = (DocumentFormat.MARKDOWN, DocumentFormat.TXT)

    def load(self, content: bytes, metadata: DocumentMetadata) -> CanonicalPolicyDocument:
        return self.load_text(decode_utf8(content), metadata)

    def load_text(self, raw_text: str, metadata: DocumentMetadata) -> CanonicalPolicyDocument:
        builder = CanonicalDocumentBuilder(
            metadata,
            parser_profile=self.parser_profile,
            parser_version=self.parser_version,
        )
        lines = split_lines(raw_text)
        index = 0
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                index += 1
                continue
            if _FENCE.match(line):
                index = self._code(builder, lines, index)
            elif (match := _HEADING.match(line)) is not None:
                builder.heading(len(match.group(1)), match.group(2), _locator(index))
                index += 1
            elif _TABLE_ROW.match(line) and self._is_table_start(lines, index):
                index = self._table(builder, lines, index)
            elif _QUOTE.match(line):
                index = self._run(builder, lines, index, BlockType.QUOTE, _QUOTE)
            elif _LIST_ITEM.match(line):
                index = self._list_item(builder, lines, index)
            else:
                index = self._paragraph(builder, lines, index)
        return builder.build()

    @staticmethod
    def _is_table_start(lines: list[str], index: int) -> bool:
        return index + 1 < len(lines) and bool(_TABLE_DELIMITER.match(lines[index + 1]))

    @staticmethod
    def _code(builder: CanonicalDocumentBuilder, lines: list[str], index: int) -> int:
        fence = _FENCE.match(lines[index]).group(1)
        end = index + 1
        while end < len(lines) and not lines[end].strip().startswith(fence):
            end += 1
        end = min(end + 1, len(lines))
        builder.block(BlockType.CODE, "\n".join(lines[index:end]), _locator(index))
        return end

    @staticmethod
    def _table(builder: CanonicalDocumentBuilder, lines: list[str], index: int) -> int:
        end = index
        while end < len(lines) and _TABLE_ROW.match(lines[end]):
            end += 1
        builder.block(BlockType.TABLE, "\n".join(lines[index:end]), _locator(index))
        return end

    @staticmethod
    def _run(
        builder: CanonicalDocumentBuilder,
        lines: list[str],
        index: int,
        block_type: BlockType,
        pattern: re.Pattern[str],
    ) -> int:
        end = index
        while end < len(lines) and pattern.match(lines[end]):
            end += 1
        builder.block(block_type, "\n".join(lines[index:end]), _locator(index))
        return end

    @staticmethod
    def _list_item(builder: CanonicalDocumentBuilder, lines: list[str], index: int) -> int:
        """목록 항목 하나. 이어지는 들여쓰기 줄은 같은 항목으로 붙인다."""
        end = index + 1
        while end < len(lines):
            following = lines[end]
            if not following.strip() or _LIST_ITEM.match(following) or _HEADING.match(following):
                break
            if not following.startswith((" ", "\t")):
                break
            end += 1
        builder.block(BlockType.LIST_ITEM, "\n".join(lines[index:end]), _locator(index))
        return end

    @staticmethod
    def _paragraph(builder: CanonicalDocumentBuilder, lines: list[str], index: int) -> int:
        end = index + 1
        while end < len(lines):
            following = lines[end]
            if not following.strip():
                break
            if (
                _HEADING.match(following)
                or _LIST_ITEM.match(following)
                or _FENCE.match(following)
                or _QUOTE.match(following)
                or _TABLE_ROW.match(following)
            ):
                break
            end += 1
        builder.block(BlockType.PARAGRAPH, "\n".join(lines[index:end]), _locator(index))
        return end


def _locator(line_index: int) -> SourceLocator:
    return SourceLocator.of("md", line=line_index + 1)
