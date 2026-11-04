"""文章搜索的纯函数工具：关键词拆分、LIKE 转义、富文本摘要与命中字段识别。"""
import html
import re
from typing import Optional


def split_terms(keyword: str) -> list[str]:
    """按空白拆分关键词并去重（大小写不敏感），保留首次出现的大小写。"""
    seen: set[str] = set()
    terms: list[str] = []
    for term in keyword.split():
        key = term.lower()
        if key not in seen:
            seen.add(key)
            terms.append(term)
    return terms


def escape_like(value: str) -> str:
    """转义 LIKE 通配符，避免用户输入的 % / _ / \\ 被当作模式语法。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def strip_html(value: str) -> str:
    """富文本转纯文本：去标签、反转义实体、压缩空白，供摘要展示使用。"""
    text = re.sub(r"<[^>]*>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _find_first_match(text: str, terms: list[str]) -> Optional[tuple[int, int]]:
    """返回最早出现的关键词位置与长度；未命中返回 None。"""
    lowered = text.lower()
    matches = [
        (position, len(term))
        for term in terms
        if (position := lowered.find(term.lower())) >= 0
    ]
    if not matches:
        return None
    return min(matches, key=lambda item: item[0])


def build_snippet(
    content: Optional[str],
    terms: list[str],
    *,
    before: int = 40,
    after: int = 60,
) -> Optional[str]:
    """截取正文中最早命中关键词的上下文（纯文本，首尾用省略号标记截断）。

    未提供正文或未命中关键词时返回 None；高亮由前端根据 matched_terms 自行完成。
    """
    if not content:
        return None
    text = strip_html(content)
    if not text:
        return None
    found = _find_first_match(text, terms)
    if found is None:
        return None
    position, matched_length = found
    start = max(0, position - before)
    end = min(len(text), position + matched_length + after)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = f"…{snippet}"
    if end < len(text):
        snippet = f"{snippet}…"
    return snippet


def matched_fields(
    title: Optional[str], content: Optional[str], terms: list[str], scope: str
) -> list[str]:
    """按搜索范围返回实际命中的字段（title/content），供前端展示命中标识。"""
    title_text = title or ""
    content_text = strip_html(content or "")
    fields: list[str] = []
    if scope in ("all", "title") and any(
        term.lower() in title_text.lower() for term in terms
    ):
        fields.append("title")
    if scope in ("all", "content") and any(
        term.lower() in content_text.lower() for term in terms
    ):
        fields.append("content")
    return fields
