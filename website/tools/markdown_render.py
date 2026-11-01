"""Render the repository's guides as web pages.

The guides in ``docs/`` are written for people reading them in the
repository. They are the single source of truth, and the site renders them
verbatim rather than keeping a second copy.

Raw HTML in a guide is not passed through: the guides are repository
content, and a page that renders unfiltered markup from a file is a page
that can be injected into. Fenced code is highlighted here, at build time,
so highlighting costs no client-side JavaScript.
"""

from __future__ import annotations

import posixpath
import re
from html import escape
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

REPO_URL = "https://github.com/alehar9320/agentic-odi/blob/main"

_MARKDOWN = MarkdownIt("commonmark", {"html": False, "linkify": True})
_MARKDOWN.enable("table")
_MARKDOWN.enable("strikethrough")

_STYLE = "monokai"
_FORMATTER = HtmlFormatter(style=_STYLE, nowrap=True)


def _highlight_code(code: str, language: str) -> str:
    """Highlight a fenced code block, falling back to plain text."""
    lexer = None
    if language:
        try:
            lexer = get_lexer_by_name(language, stripall=False)
        except ClassNotFound:
            lexer = None
    if lexer is None:
        try:
            lexer = guess_lexer(code)
        except ClassNotFound:
            lexer = None
    if lexer is None:
        return ""
    return highlight(code, lexer, _FORMATTER)


def _fence_renderer(markdown: MarkdownIt) -> None:
    """Render fenced code with server-side syntax highlighting.

    A ``mermaid`` fence is the exception. It is not code to colour but a
    diagram's source, and colouring it would be wrong twice over: the reader
    wants the picture, and the pygments mermaid lexer is not the renderer. The
    source is emitted escaped, so a page whose script never loads still shows
    the diagram as text, and ``assets/diagrams.js`` replaces it with the drawing
    where it does. That is the one place the site spends client-side JavaScript,
    and only pages with a diagram ask for it.
    """

    def render(tokens: list, index: int, options, env, **kwargs) -> str:  # noqa: ANN001
        token = tokens[index]
        info = (token.info or "").strip()
        language = info.split()[0] if info else ""
        if language == "mermaid":
            return f'<pre class="mermaid">{escape(token.content)}</pre>'
        markup = _highlight_code(token.content, language)
        if not markup:
            return ""
        return f'<pre class="highlight"><code class="language-{language}">{markup}</code></pre>'

    renderer: Any = markdown.renderer
    renderer.rules["fence"] = render


def _heading_renderer(markdown: MarkdownIt) -> None:
    """Give every heading a stable anchor, the way GitHub does.

    A guide's own top-level heading is the page's title, and the template
    renders it. So a level-one heading inside the body is demoted to level
    two, and the page keeps exactly one ``<h1>``.

    Each heading also ends in a link to itself, so a reader can send someone
    straight to a section instead of the top of the page.
    """

    def render_open(tokens: list, index: int, options, env, **kwargs) -> str:  # noqa: ANN001
        token = tokens[index]
        level = int(token.tag[1])
        if level == 1:
            level = 2
        # The heading's text is in the inline token that follows the open tag.
        text = token.content
        if not text and index + 1 < len(tokens):
            text = tokens[index + 1].content
        anchor = _unique_anchor(env, text)
        env["heading_open_anchor"] = (anchor, level)
        return f'<h{level} id="{anchor}">'

    def render_close(tokens: list, index: int, options, env, **kwargs) -> str:  # noqa: ANN001
        anchor, level = env.pop("heading_open_anchor", (None, 2))
        if anchor is None:
            return tokens[index].tag
        return (
            f'<a class="heading-anchor" href="#{anchor}"'
            ' aria-label="Copy link to this section" title="Copy link">#</a>'
            f"</h{level}>"
        )

    renderer: Any = markdown.renderer
    renderer.rules["heading_open"] = render_open
    renderer.rules["heading_close"] = render_close


def _unique_anchor(env: dict, text: str) -> str:
    """A heading anchor, unique within the page."""
    counts = env.setdefault("heading_anchors", {})
    base = slugify(text)
    count = counts.get(base, 0)
    counts[base] = count + 1
    return base if not count else f"{base}-{count}"


_fence_renderer(_MARKDOWN)
_heading_renderer(_MARKDOWN)


def slugify(text: str) -> str:
    """A GitHub-compatible heading anchor."""
    anchor = text.strip().lower()
    anchor = re.sub(r"[^\w\- ]+", "", anchor)
    return re.sub(r"[\s_]+", "-", anchor).strip("-")


def _rewrite_links(
    html: str,
    *,
    source_path: str,
    link_map: dict[str, str],
    page_path: str,
) -> str:
    """Point a guide's relative links at the site, or at GitHub.

    The guides are written for the repository, so they link to ``.md`` files.
    On the site those files are pages under a different URL. Resolve the
    link relative to the guide that contains it, map it to the rendered page
    when one exists, and fall back to the repository for guides the site does
    not publish. Absolute links and in-page anchors are left alone.
    """
    source_dir = posixpath.dirname(source_path)
    page_dir = posixpath.dirname(page_path)

    def replace(match: re.Match[str]) -> str:
        href = match.group(1)
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", href, re.IGNORECASE):
            return match.group(0)

        target, _, fragment = href.partition("#")
        target = target.split("?", 1)[0]
        resolved = posixpath.normpath(posixpath.join(source_dir, target))
        suffix = f"#{fragment}" if fragment else ""

        if resolved in link_map:
            destination = posixpath.relpath(link_map[resolved], page_dir)
            if destination.endswith("index.html"):
                destination = destination[: -len("index.html")]
            return f'href="{destination}{suffix}"'

        return f'href="{REPO_URL}/{resolved}{suffix}"'

    return re.sub(r'href="([^"]+)"', replace, html)


def render(
    md: str,
    *,
    source_path: str | None = None,
    link_map: dict[str, str] | None = None,
    page_path: str | None = None,
) -> str:
    """A guide's prose, as HTML, with a link back to its source."""
    html = _MARKDOWN.render(md)

    if source_path and link_map is not None and page_path is not None:
        html = _rewrite_links(
            html,
            source_path=source_path,
            link_map=link_map,
            page_path=page_path,
        )

    if source_path:
        html += (
            '\n<p class="prose__source">Source of truth: '
            f"<code>{source_path}</code> &mdash; "
            f'<a href="{REPO_URL}/{source_path}">view on GitHub</a></p>'
        )
    return html


def headings(html: str) -> list[dict[str, str]]:
    """The headings in a rendered page, for a table of contents."""
    found: list[dict[str, str]] = []
    for match in re.finditer(r'<h([23]) id="([^"]+)">(.*?)</h\1>', html, re.DOTALL):
        # The section link is decoration, not part of the heading's name.
        body = re.sub(r'<a class="heading-anchor".*?</a>', "", match.group(3), flags=re.DOTALL)
        found.append(
            {
                "level": match.group(1),
                "anchor": match.group(2),
                "text": re.sub(r"<[^>]+>", "", body).strip(),
            }
        )
    return found


def read_guide(path: Path) -> str:
    """The raw markdown of a guide."""
    return path.read_text(encoding="utf-8")


def take_title(md: str) -> tuple[str, str | None]:
    """A guide's own title, and the body without it.

    The template renders the page's ``<h1>``. When the guide opens with its
    own top-level heading, that heading *is* the page title, so it is lifted
    out of the body rather than rendered a second time.
    """
    lines = md.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            del lines[index]
            return "\n".join(lines), title
        if line.strip():
            break
    return md, None
