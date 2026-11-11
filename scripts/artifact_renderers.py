"""Which code in this repository renders an artifact, and what became of it.

ALH-238 asked for "the renderer inventory": a list a reader can consult to see
every artifact the product emits, whether it has been through the structural
audit in `artifact_a11y.py`, and who owns the fix when it has not.

An inventory kept in prose rots, and it rots quietly — the person who adds a
renderer is the person who would have to remember to edit the prose. So the
inventory is data, and `discover_html_emitters` is the gate: it scans the
directories an artifact can come from for the markup that gives a renderer away,
and a test fails if the scan finds anything the inventory does not name. The
scan is deliberately blunt. It is a net cast for the mistake nobody thought to
write down, not a classification of the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

STATUSES: Final[tuple[str, ...]] = ("emits-html", "emits-markdown", "absent")

#: The directories an artifact can be rendered from. Narrow on purpose: the
#: studio's own components render the app's interface, which axe and the design
#: system govern, and sweeping them here would bury the artifacts under markup
#: that is not an artifact.
ARTIFACT_ROOTS: Final[tuple[str, ...]] = (
    "website/tools",
    "website/templates",
    "apps/studio/public",
    "apps/studio/src/lib",
    "apps/studio/src/components/brief",
    "apps/studio/src/components/canvas",
    "brand/tools",
)

#: The strings that betray a renderer: the beginning of a document, the element
#: a table or a heading is written with, and the role a chart takes on.
MARKUP_SIGNALS: Final[tuple[str, ...]] = ("<h1", "<table", "<!DOCTYPE", 'role="img"')

_SKIPPED_DIRECTORIES: Final[frozenset[str]] = frozenset({"dist", "node_modules", "__pycache__"})
_TEXT_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".ts", ".tsx", ".html", ".js", ".mjs"})


@dataclass(frozen=True)
class Renderer:
    """One row of the inventory.

    `status` is what the source actually does, not what the issue wished for:
    `emits-html` writes markup, `emits-markdown` writes prose that becomes
    markup somewhere else, and `absent` means the artifact has no renderer yet —
    which is recorded rather than claimed, so `fixes_owned_by` names the issue
    that has to build it.
    """

    name: str
    path: str
    language: str
    status: str
    fixes_owned_by: str


RENDERERS: Final[tuple[Renderer, ...]] = (
    # The website: generated at build time, audited by website/tests/test_site.py.
    Renderer("docs guide", "website/tools/markdown_render.py", "python", "emits-html", "ALH-238"),
    Renderer("site shell", "website/tools/build_site.py", "python", "emits-html", "ALH-238"),
    Renderer("page skeleton", "website/templates/base.html", "html", "emits-html", "ALH-238"),
    Renderer("landing page", "website/templates/landing.html", "html", "emits-html", "ALH-238"),
    Renderer("guide page", "website/templates/doc.html", "html", "emits-html", "ALH-238"),
    Renderer("docs index", "website/templates/docs_index.html", "html", "emits-html", "ALH-238"),
    Renderer("not-found page", "website/templates/404.html", "html", "emits-html", "ALH-238"),
    Renderer("sample workspace", "website/templates/sample.html", "html", "emits-html", "ALH-238"),
    Renderer("quick start", "website/templates/_quick_start.html", "html", "emits-html", "ALH-238"),
    Renderer("social cards", "website/tools/make_og.py", "python", "emits-html", "ALH-238"),
    Renderer(
        "connector reference",
        "website/templates/_connector_reference.html",
        "html",
        "emits-html",
        "ALH-238",
    ),
    Renderer(
        "mcp reference", "website/templates/_mcp_reference.html", "html", "emits-html", "ALH-238"
    ),
    # The studio: rendered in the browser, audited by axe and by its own tests.
    Renderer("offline shell", "apps/studio/public/offline.html", "html", "emits-html", "ALH-238"),
    Renderer(
        "decision brief",
        "apps/studio/src/lib/export.ts",
        "typescript",
        "emits-markdown",
        "ALH-238",
    ),
    Renderer(
        "brief preview",
        "apps/studio/src/components/brief/BriefLens.tsx",
        "typescript",
        "emits-markdown",
        "ALH-238",
    ),
    Renderer(
        "evidence chart",
        "apps/studio/src/components/canvas/OpportunityLandscape.tsx",
        "typescript",
        "emits-html",
        "ALH-238",
    ),
    # Asked for by the issue, not built by anything. ALH-252 gives them a renderer.
    Renderer("memo", "", "typescript", "absent", "ALH-252"),
    Renderer("one-pager", "", "typescript", "absent", "ALH-252"),
    Renderer("shared page", "", "typescript", "absent", "ALH-252"),
)


def discover_html_emitters(root: Path = REPO_ROOT) -> set[str]:
    """Every file under an artifact root that writes markup, repo-relative.

    A path is returned only when the file contains one of `MARKUP_SIGNALS`.
    Tests, snapshots and build output are skipped: they are copies of markup,
    not renderers of it, and registering them would make the inventory a list of
    everything that exists rather than everything that emits.
    """
    found: set[str] = set()
    for directory in ARTIFACT_ROOTS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not _is_source(path, root) or not _emits_markup(path):
                continue
            found.add(path.relative_to(root).as_posix())
    return found


def _is_source(path: Path, root: Path) -> bool:
    if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
        return False
    relative = path.relative_to(root)
    if any(part in _SKIPPED_DIRECTORIES for part in relative.parts[:-1]):
        return False
    return ".test." not in path.name and ".snap" not in path.suffix


def _emits_markup(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return any(signal in text for signal in MARKUP_SIGNALS)
