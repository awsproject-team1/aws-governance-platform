"""HTML Loader. 사내 위키 Export를 대상으로 한다.

먼저 위험 요소를 통째로 버린 뒤 heading/목록/표 중심으로 DOM을 변환한다. 버리는
것은 실행 가능한 요소와 외부 자원 참조다: ``script``, ``style``, ``iframe``,
``object``, ``embed``, ``svg``, ``form``, ``link``, ``meta``, ``base`` 등.

속성은 구조에 필요한 것만 남긴다. 표 병합(``colspan``/``rowspan``)과 ``a[href]``만
읽고 나머지는 버린다. ``javascript:``/``data:`` href는 남기지 않는다.

Text 정규화는 HTML 의미를 따른다. ``pre`` 밖에서는 연속 공백을 하나로 줄이고
``br``은 줄바꿈으로 바꾼다. 이 규칙이 없으면 markup 들여쓰기가 그대로 해시에 들어간다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from ...errors import GovernanceValidationError
from ..canonical_document import (
    BlockType,
    CanonicalDocumentBuilder,
    CanonicalPolicyDocument,
    DocumentFormat,
    DocumentMetadata,
    SourceLocator,
)
from ..upload import decode_utf8
from .base import DocumentLoader, ExtractionError

#: 하위 내용까지 통째로 버리는 요소.
DROPPED_TAGS = frozenset(
    {
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "applet",
        "svg",
        "canvas",
        "audio",
        "video",
        "form",
        "input",
        "button",
        "select",
        "textarea",
        "noscript",
        "template",
        "link",
        "meta",
        "base",
        "head",
    }
)

VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
)

CONTAINER_TAGS = frozenset(
    {
        "html",
        "body",
        "div",
        "section",
        "article",
        "main",
        "header",
        "footer",
        "nav",
        "aside",
        "dl",
        "details",
        "figure",
        "fieldset",
        "document",
    }
)

_BLOCK_LEVEL = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "dl",
        "fieldset",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "ul",
    }
)

#: 닫지 않은 tag를 만났을 때 암묵적으로 닫는 규칙. 위키 Export는 ``<p>``를 자주 열어둔다.
_IMPLIED_CLOSE: dict[str, frozenset[str]] = {
    "p": _BLOCK_LEVEL,
    **{f"h{level}": _BLOCK_LEVEL for level in range(1, 7)},
    "li": frozenset({"li"}),
    "dt": frozenset({"dt", "dd"}),
    "dd": frozenset({"dt", "dd"}),
    "td": frozenset({"td", "th", "tr"}),
    "th": frozenset({"td", "th", "tr"}),
    "tr": frozenset({"tr"}),
}

_HEADING_TAGS = {f"h{level}": level for level in range(1, 7)}
_PARAGRAPH_TAGS = frozenset({"p", "dt", "dd", "figcaption", "address", "summary"})
_LIST_TAGS = frozenset({"ul", "ol"})
_SAFE_HREF = re.compile(r"^(https?://|mailto:|#|/|\./|\.\./)", re.IGNORECASE)
_WHITESPACE = re.compile(r"[ \t\f\v]+")


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[object] = field(default_factory=list)
    path: str = ""


# DOM 중첩 상한.
#
# `_walk`/`_emit`은 서로 재귀하고 `_inline_text`, `_raw_text`, `_find`, `_render_table`도
# 자식으로 재귀한다. 상한이 없으면 몇 KB짜리 중첩 HTML 하나가 RecursionError를 내는데,
# 이는 LoaderError 계약 밖이라 거부도 경고도 아닌 크래시가 된다. 신뢰할 수 없는 업로드
# 경로이므로 Tree를 만드는 시점에서 한 번 막는다. 여기서 막으면 아래 모든 walker가 함께
# 보호되고, walker를 새로 추가할 때 가드를 빠뜨릴 여지도 없다.
#
# 실제 사내 규정 문서는 표 안의 목록까지 세어도 수십 단계를 넘지 않는다. 100은 정상 문서를
# 자르지 않으면서 walker 두 개가 겹쳐도(100 x 2 프레임) Python 기본 재귀 한도 안에 든다.
MAX_DOM_DEPTH = 100


class _TreeParser(HTMLParser):
    """관대한 파서. 닫히지 않은 tag를 만나도 남은 문서를 버리지 않는다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("document")
        self._stack: list[_Node] = [self.root]
        self._counts: list[dict[str, int]] = [{}]
        self.dropped: dict[str, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in DROPPED_TAGS:
            self.dropped[tag] = self.dropped.get(tag, 0) + 1
        while len(self._stack) > 1 and tag in _IMPLIED_CLOSE.get(self._stack[-1].tag, ()):
            self._stack.pop()
            self._counts.pop()
        if len(self._stack) > MAX_DOM_DEPTH:
            raise ExtractionError(f"HTML 중첩이 상한을 넘었다: {MAX_DOM_DEPTH}단계 (tag={tag})")
        node = _Node(tag=tag, attrs={key: value or "" for key, value in attrs})
        parent = self._stack[-1]
        counts = self._counts[-1]
        counts[tag] = counts.get(tag, 0) + 1
        step = f"{tag}[{counts[tag]}]"
        node.path = f"{parent.path}>{step}" if parent.path else step
        parent.children.append(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)
            self._counts.append({})

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for depth in range(len(self._stack) - 1, 0, -1):
            if self._stack[depth].tag == tag:
                del self._stack[depth:]
                del self._counts[depth:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)


class HtmlLoader(DocumentLoader):
    parser_profile = "html-dom-loader"
    parser_version = "1"
    supported_formats = (DocumentFormat.HTML,)

    def load(self, content: bytes, metadata: DocumentMetadata) -> CanonicalPolicyDocument:
        return self.load_text(decode_utf8(content), metadata)

    def load_text(self, raw_text: str, metadata: DocumentMetadata) -> CanonicalPolicyDocument:
        parser = _TreeParser()
        try:
            parser.feed(raw_text)
            parser.close()
        except ExtractionError:
            # ExtractionError는 ValueError 계열이라 아래 handler가 삼킨다. 중첩 상한처럼
            # 구체적인 사유가 "파싱할 수 없다"로 뭉개지지 않게 그대로 올린다.
            raise
        except (AssertionError, ValueError) as exc:  # 손상된 markup
            raise ExtractionError("HTML을 파싱할 수 없다") from exc

        builder = CanonicalDocumentBuilder(
            metadata,
            parser_profile=self.parser_profile,
            parser_version=self.parser_version,
        )
        for tag, count in sorted(parser.dropped.items()):
            builder.warn(f"실행 가능 요소를 제거했다: {tag} x{count}")
        self._walk(parser.root, builder, list_depth=0)
        return builder.build()

    def _walk(self, node: _Node, builder: CanonicalDocumentBuilder, *, list_depth: int) -> None:
        pending: list[object] = []

        def flush() -> None:
            """Block 요소로 감싸이지 않은 채 컨테이너에 흘러 있는 텍스트를 문단으로 낸다."""
            if not pending:
                return
            text = _inline_text(pending, builder)
            pending.clear()
            if text.strip():
                builder.block(BlockType.PARAGRAPH, text, _locator(node.path or "document"))

        for child in node.children:
            if isinstance(child, str):
                pending.append(child)
                continue
            if child.tag in DROPPED_TAGS:
                continue
            if child.tag in _INLINE_TAGS:
                pending.append(child)
                continue

            flush()
            self._emit(child, builder, list_depth=list_depth)
        flush()

    def _emit(self, node: _Node, builder: CanonicalDocumentBuilder, *, list_depth: int) -> None:
        tag = node.tag
        locator = _locator(node.path)
        if tag in _HEADING_TAGS:
            builder.heading(_HEADING_TAGS[tag], _inline_text(node.children, builder), locator)
        elif tag in _PARAGRAPH_TAGS:
            builder.block(BlockType.PARAGRAPH, _inline_text(node.children, builder), locator)
        elif tag == "blockquote":
            builder.block(BlockType.QUOTE, _inline_text(node.children, builder), locator)
        elif tag == "pre":
            builder.block(BlockType.CODE, _raw_text(node.children), locator)
        elif tag in _LIST_TAGS:
            self._walk(node, builder, list_depth=list_depth + 1)
        elif tag == "li":
            self._list_item(node, builder, list_depth=list_depth)
        elif tag == "table":
            builder.block(BlockType.TABLE, _render_table(node, builder), locator)
        elif tag in CONTAINER_TAGS:
            self._walk(node, builder, list_depth=list_depth)
        elif tag == "hr":
            return
        else:
            self._walk(node, builder, list_depth=list_depth)

    def _list_item(
        self, node: _Node, builder: CanonicalDocumentBuilder, *, list_depth: int
    ) -> None:
        """항목 자신의 텍스트를 먼저 내고 중첩 목록/표는 따로 낸다.

        들여쓰기로 깊이를 보존한다. 중첩을 잃으면 "상위 항목의 예외"가 상위 항목의
        본문처럼 읽힌다.
        """
        own = [child for child in node.children if not _is_block_child(child)]
        nested = [child for child in node.children if _is_block_child(child)]
        indent = "  " * max(list_depth - 1, 0)
        text = _inline_text(own, builder)
        if text.strip():
            builder.block(BlockType.LIST_ITEM, f"{indent}- {text}", _locator(node.path))
        for child in nested:
            if isinstance(child, _Node) and child.tag not in DROPPED_TAGS:
                self._emit(child, builder, list_depth=list_depth)


_INLINE_TAGS = frozenset(
    {
        "a",
        "span",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "code",
        "small",
        "sub",
        "sup",
        "mark",
        "abbr",
        "time",
        "br",
        "img",
        "label",
        "font",
    }
)


def _is_block_child(child: object) -> bool:
    return isinstance(child, _Node) and child.tag in (_LIST_TAGS | {"table", "pre", "blockquote"})


def _inline_text(children: list[object], builder: CanonicalDocumentBuilder | None) -> str:
    parts: list[str] = []
    for child in children:
        if isinstance(child, str):
            parts.append(child)
            continue
        if child.tag in DROPPED_TAGS:
            continue
        if child.tag == "br":
            parts.append("\n")
            continue
        inner = _inline_text(child.children, builder)
        if child.tag == "a":
            href = child.attrs.get("href", "").strip()
            if href and not _SAFE_HREF.match(href):
                if builder is not None:
                    builder.warn(f"안전하지 않은 링크를 제거했다: {href.split(':', 1)[0]}:")
                href = ""
            if href and href not in inner:
                inner = f"{inner} ({href})" if inner.strip() else href
        parts.append(inner)
    text = "".join(parts)
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def _raw_text(children: list[object]) -> str:
    parts: list[str] = []
    for child in children:
        if isinstance(child, str):
            parts.append(child)
        elif child.tag not in DROPPED_TAGS:
            parts.append(_raw_text(child.children))
    return "".join(parts)


def _render_table(node: _Node, builder: CanonicalDocumentBuilder) -> str:
    """표를 행/열 위치를 지킨 격자로 편다.

    ``colspan``/``rowspan``으로 병합된 셀은 시작 위치에만 값을 두고 나머지 칸은 빈
    칸으로 남긴다. 병합을 무시하고 그냥 이어 붙이면 열이 밀려 다른 항목의 값으로 읽힌다.
    """
    grid: list[list[str]] = []
    occupied: set[tuple[int, int]] = set()
    for row_index, row in enumerate(_find(node, "tr")):
        while len(grid) <= row_index:
            grid.append([])
        column = 0
        for cell in _find(row, "td", "th"):
            while (row_index, column) in occupied:
                column += 1
            text = _inline_text(cell.children, builder).replace("\n", " ").replace("|", "\\|")
            span_x = _span(cell, "colspan")
            span_y = _span(cell, "rowspan")
            for offset_y in range(span_y):
                for offset_x in range(span_x):
                    occupied.add((row_index + offset_y, column + offset_x))
                    while len(grid) <= row_index + offset_y:
                        grid.append([])
                    target = grid[row_index + offset_y]
                    while len(target) <= column + offset_x:
                        target.append("")
            grid[row_index][column] = text
            column += span_x
    width = max((len(row) for row in grid), default=0)
    return "\n".join(
        "| " + " | ".join(row + [""] * (width - len(row))) + " |" for row in grid if row or width
    )


def _span(cell: _Node, name: str) -> int:
    raw = cell.attrs.get(name, "1").strip()
    if not raw.isdigit():
        return 1
    return max(1, min(int(raw), 64))


def _find(node: _Node, *tags: str) -> list[_Node]:
    """중첩된 표를 넘겨다보지 않고 가까운 자손만 찾는다."""
    found: list[_Node] = []
    for child in node.children:
        if not isinstance(child, _Node) or child.tag in DROPPED_TAGS:
            continue
        if child.tag in tags:
            found.append(child)
        elif child.tag not in ("table",):
            found.extend(_find(child, *tags))
    return found


def _locator(path: str) -> SourceLocator:
    if not path:
        raise GovernanceValidationError("HTML block에 DOM 경로가 없다")
    return SourceLocator.of("html", dom=path)
