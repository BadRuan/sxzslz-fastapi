"""搜索纯函数工具测试：分词、LIKE 转义、富文本去标签、摘要截取、命中字段。"""
from app.utils.search import (
    build_snippet,
    escape_like,
    matched_fields,
    split_terms,
    strip_html,
)


def test_split_terms_splits_dedupes_and_keeps_first_case():
    assert split_terms("  泵站   托管 泵站 FastAPI fastapi ") == [
        "泵站",
        "托管",
        "FastAPI",
    ]


def test_split_terms_returns_empty_list_for_whitespace():
    assert split_terms(" \t\n ") == []


def test_escape_like_escapes_wildcards_and_backslash():
    assert escape_like("100%_a\\b") == "100\\%\\_a\\\\b"


def test_strip_html_removes_tags_unescapes_entities_and_collapses_whitespace():
    assert strip_html("<p>a&nbsp;&amp; b</p><p>c</p>") == "a & b c"


def test_build_snippet_returns_context_with_ellipsis():
    content = "前缀" * 30 + "泵站托管" + "后缀" * 40
    snippet = build_snippet(content, ["泵站"])

    assert snippet is not None
    assert "泵站托管" in snippet
    assert snippet.startswith("…")
    assert snippet.endswith("…")


def test_build_snippet_returns_none_when_content_or_match_missing():
    assert build_snippet(None, ["泵站"]) is None
    assert build_snippet("", ["泵站"]) is None
    assert build_snippet("正文", ["不存在"]) is None


def test_build_snippet_strips_html_and_matches_case_insensitively():
    snippet = build_snippet("<p>Hello <strong>FastAPI</strong> world</p>", ["fastapi"])
    assert snippet == "Hello FastAPI world"


def test_build_snippet_keeps_output_plain_text_for_xss_content():
    snippet = build_snippet(
        "<p>正文</p><script>alert('泵站')</script>", ["泵站"]
    )
    assert snippet is not None
    assert "<script>" not in snippet
    assert "泵站" in snippet


def test_matched_fields_respects_scope_and_case():
    assert matched_fields("FastAPI 指南", "<p>正文</p>", ["fastapi"], "all") == [
        "title"
    ]
    assert matched_fields("标题", "正文", ["正文"], "title") == []
    assert matched_fields("标题", "正文", ["正文"], "content") == ["content"]
