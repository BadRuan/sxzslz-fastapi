from mistune import HTMLRenderer, escape, create_markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import html
from pygments.util import ClassNotFound


class HighlightRenderer(HTMLRenderer):
    def block_code(self, code, info=None):
        code = code.strip()
        if info:
            try:
                # 根据 markdown 中指定的语言（如 ```python）获取对应的词法分析器
                lexer = get_lexer_by_name(info, stripall=True)
            except ClassNotFound:
                # 如果找不到对应的语言，直接返回纯文本代码块
                return f'<pre><code>{escape(code)}</code></pre>'
            # 使用 Pygments 生成带语法高亮的 HTML
            formatter = html.HtmlFormatter(cssclass="highlight")
            return highlight(code, lexer, formatter)
        # 没有指定语言时，返回普通代码块
        return f'<pre><code>{escape(code)}</code></pre>'

def markdown_to_html(markdown_text):
    renderer = HighlightRenderer()
    # 启用表格(table)等常用插件
    markdown = create_markdown(renderer=renderer, plugins=['strikethrough', 'url', 'table'])
    return markdown(markdown_text)
