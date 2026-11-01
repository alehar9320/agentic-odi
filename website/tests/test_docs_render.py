"""The markdown pipeline: the repository's guides must render faithfully."""

from __future__ import annotations

import re

import markdown_render
from site_support import _built_root, all_pages, read_page


def test_markdown_features_render():
    html = markdown_render.render(
        "# Title\n\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n\n"
        "- one\n  - nested\n\n"
        "```python\nprint('hi')\n```\n",
        source_path="docs/example.md",
    )
    assert "<table>" in html
    assert "<ul>" in html
    assert "nested" in html
    assert "<pre" in html and "print" in html
    assert 'class="highlight"' in html


def test_markdown_does_not_pass_through_raw_html():
    html = markdown_render.render(
        "<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n",
        source_path="docs/x.md",
    )
    # The tags are escaped, so they are inert text rather than markup.
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html


def test_headings_get_anchors():
    html = markdown_render.render("## First section\n\n## Second section\n")
    assert 'id="first-section"' in html
    assert 'id="second-section"' in html


def test_each_heading_links_to_itself():
    html = markdown_render.render("## First section\n\n### Deeper detail\n")

    assert html.count('class="heading-anchor"') == 2
    assert 'href="#first-section"' in html
    assert 'href="#deeper-detail"' in html
    assert 'aria-label="Copy link to this section"' in html


def test_duplicate_headings_link_to_their_own_anchor():
    html = markdown_render.render("## Setup\n\n## Setup\n")

    assert 'href="#setup"' in html
    assert 'href="#setup-1"' in html


def test_the_section_link_is_not_part_of_the_heading_text():
    html = markdown_render.render("## Install the CLI\n")

    assert markdown_render.headings(html) == [
        {"level": "2", "anchor": "install-the-cli", "text": "Install the CLI"}
    ]


def test_duplicate_headings_get_unique_anchors():
    html = markdown_render.render("## Setup\n\n## Setup\n")
    assert 'id="setup"' in html
    assert 'id="setup-1"' in html


def test_a_guides_own_title_is_lifted_out_of_the_body():
    body, title = markdown_render.take_title("# Running The Living Studio\n\nProse.\n")
    assert title == "Running The Living Studio"
    assert "# Running The Living Studio" not in body
    assert "Prose." in body


def test_a_guide_without_a_title_is_left_alone():
    body, title = markdown_render.take_title("Prose first.\n\n# Later heading\n")
    assert title is None
    assert body.startswith("Prose first.")


def test_the_rendered_guide_links_to_its_source():
    html = markdown_render.render("Prose.\n", source_path="docs/cli.md")
    assert "docs/cli.md" in html
    assert "https://github.com/alehar9320/agentic-odi/blob/main/docs/cli.md" in html


def test_guide_links_resolve_to_the_rendered_pages():
    html = markdown_render.render(
        "See [the studio](living-studio.md#the-room).\n",
        source_path="docs/local-llm.md",
        link_map={"docs/living-studio.md": "docs/studio/index.html"},
        page_path="docs/local-llm/index.html",
    )
    assert 'href="../studio/#the-room"' in html


def test_unpublished_guides_link_back_to_the_repository():
    html = markdown_render.render(
        "See [data flow](data-flow.md).\n",
        source_path="docs/architecture/README.md",
        link_map={"docs/architecture/README.md": "docs/architecture/index.html"},
        page_path="docs/architecture/index.html",
    )
    assert (
        "https://github.com/alehar9320/agentic-odi/blob/main/docs/architecture/data-flow.md" in html
    )


def test_a_mermaid_fence_is_a_diagram_not_highlighted_code():
    html = markdown_render.render('```mermaid\ngraph BT\n    a["core"] --> b["cli"]\n```\n')
    assert '<pre class="mermaid">' in html
    assert 'class="highlight"' not in html


def test_diagram_source_is_escaped_until_the_renderer_draws_it():
    html = markdown_render.render(
        '```mermaid\nflowchart LR\n    A["<img src=x onerror=alert(1)>"] --> B\n```\n'
    )
    assert "&lt;img" in html
    assert "<img" not in html


def test_the_renderer_loads_exactly_where_a_diagram_is_drawn():
    drawn = sorted(page for page in all_pages() if '<pre class="mermaid">' in read_page(page))
    asking = sorted(page for page in all_pages() if "assets/diagrams.js" in read_page(page))
    assert drawn == asking, "a page paid for the runtime without a diagram, or lost its picture"
    assert drawn, "no guide renders a diagram any more"


def test_the_mermaid_runtime_is_vendored_rather_than_fetched():
    assert _built_root("assets/mermaid/mermaid.min.js").is_file()
    assert _built_root("assets/mermaid/LICENSE").is_file()
    fetched = [
        page
        for page in all_pages()
        if re.search(r"jsdelivr|unpkg|cdn\.js\.cloudflare", read_page(page))
    ]
    assert not fetched, f"pages reach a third-party CDN: {fetched}"
