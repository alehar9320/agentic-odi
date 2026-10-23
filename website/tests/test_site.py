# website/tests/test_site.py
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"
PAGES_URL = "https://alehar9320.github.io/agentic-odi/"

ALLOWED_EXTERNAL = {
    "https://github.com/alehar9320/agentic-odi",
    "https://github.com/alehar9320/agentic-odi/issues",
    "https://horizon.prefect.io/alhase/servers/agentic-odi/chat",
    "https://agentic-odi.alehar.workers.dev/",
    "https://docs.astral.sh/uv/",
    "https://modelcontextprotocol.io",
    PAGES_URL,
}

MILESTONE_DATE = re.compile(
    r"\b(Q[1-4]|Jan(uary)?|Feb(ruary)?|Mar(ch)?|Apr(il)?|May|Jun(e)?|"
    r"Jul(y)?|Aug(ust)?|Sep(t(ember)?)?|Oct(ober)?|Nov(ember)?|Dec(ember)?)[ -]20\d\d\b"
)

EMOJI = re.compile("[\u2600-\u27bf\U0001f300-\U0001faff]")


class Doc(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lang = None
        self.charset = False
        self.viewport = False
        self.title = ""
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.refs: list[str] = []
        self.headings: list[tuple[int, str]] = []
        self.tags: list[str] = []
        self.metas: dict[str, str] = {}
        self.theme_colors: list[tuple[str, str]] = []
        self.text: list[str] = []
        self._in_title = False
        self._heading: tuple[int, list[str]] | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            if a.get("charset"):
                self.charset = True
            if a.get("name") == "viewport":
                self.viewport = True
            if a.get("name") == "theme-color":
                self.theme_colors.append((a.get("content", ""), a.get("media", "")))
            key = a.get("property") or a.get("name")
            if key:
                self.metas[key] = a.get("content", "")
        elif tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        elif tag in ("link", "script", "img"):
            ref = a.get("href") or a.get("src")
            if ref:
                self.refs.append(ref)
        if a.get("id"):
            self.ids.add(a["id"])
        if re.fullmatch(r"h[1-6]", tag):
            self._heading = (int(tag[1]), [])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif self._heading and tag == f"h{self._heading[0]}":
            level, parts = self._heading
            self.headings.append((level, " ".join("".join(parts).split())))
            self._heading = None

    def handle_data(self, data):
        self.text.append(data)
        if self._in_title:
            self.title += data
        if self._heading:
            self._heading[1].append(data)


def parse(name: str) -> Doc:
    doc = Doc()
    doc.feed((SITE / name).read_text(encoding="utf-8"))
    return doc


def test_lang_charset_viewport():
    doc = parse("index.html")
    assert doc.lang == "en"
    assert doc.charset
    assert doc.viewport


def test_title_and_description():
    doc = parse("index.html")
    assert "Agentic ODI" in doc.title
    assert len(doc.title.strip()) <= 60
    desc = doc.metas.get("description", "")
    assert 0 < len(desc) <= 160


def test_single_h1_and_ordered_headings():
    levels = [lv for lv, _ in parse("index.html").headings]
    assert levels.count(1) == 1
    assert levels[0] == 1
    for prev, cur in zip(levels, levels[1:], strict=False):
        assert cur <= prev + 1


def test_landmarks_and_section_ids():
    doc = parse("index.html")
    for landmark in ("header", "main", "footer"):
        assert landmark in doc.tags
    assert {"problem", "insight", "how", "run", "status"} <= doc.ids


def test_no_dead_internal_anchors():
    doc = parse("index.html")
    internal = [h[1:] for h in doc.hrefs if h.startswith("#")]
    assert internal, "expected in-page anchors"
    assert set(internal) <= doc.ids


def test_local_resources_exist_and_stylesheet_present():
    doc = parse("index.html")
    local = [r for r in doc.refs if not r.startswith(("http://", "https://"))]
    assert local
    for ref in local:
        assert (SITE / ref).is_file(), f"missing resource: {ref}"
    assert "assets/style.css" in local
    assert "assets/favicon.svg" in local
    assert "assets/favicon.png" in local


def test_no_third_party_resources():
    for ref in parse("index.html").refs:
        if ref.startswith(("http://", "https://")):
            assert ref in ALLOWED_EXTERNAL, f"off-allowlist resource: {ref}"
        else:
            assert ref.startswith("assets/"), f"unexpected resource: {ref}"


def test_external_links_https_and_allowlisted():
    for href in parse("index.html").hrefs:
        if href.startswith("#"):
            continue
        assert href.startswith("https://"), href
        assert href in ALLOWED_EXTERNAL, href


def test_social_cards_and_theme_colors():
    doc = parse("index.html")
    m = doc.metas
    assert m.get("og:type") == "website"
    assert m.get("og:site_name") == "Agentic ODI"
    assert m.get("og:title") and m.get("og:description")
    assert m.get("og:url") == PAGES_URL
    assert m.get("og:image") == PAGES_URL + "assets/og.png"
    assert m.get("twitter:card") == "summary_large_image"
    assert m.get("twitter:title") and m.get("twitter:description")
    assert m.get("twitter:image") == PAGES_URL + "assets/og.png"
    assert PAGES_URL in doc.refs  # rel=canonical
    media = [m_ for _, m_ in doc.theme_colors]
    assert len(doc.theme_colors) == 2
    assert any("prefers-color-scheme: light" in x for x in media)
    assert any("prefers-color-scheme: dark" in x for x in media)


def test_honesty_contract():
    text = (SITE / "index.html").read_text(encoding="utf-8")
    low = text.lower()
    assert "experimental" in low
    assert "free prefect account" in low
    assert "all rights reserved" in low
    assert "strategyn" in low
    assert "your roadmap is a guess." in low
    assert "we don't publish dates" in low
    assert "open an issue" in low
    assert "http://localhost:8000/mcp" in text
    assert "agentic-odi.fastmcp.app" not in text
    assert "discord" not in low
    assert "mailto:" not in low


def test_no_milestone_dates():
    text = (SITE / "index.html").read_text(encoding="utf-8")
    assert not MILESTONE_DATE.search(text), "no dated milestones on an experimental product"


def test_no_emoji_on_site():
    text = (SITE / "index.html").read_text(encoding="utf-8")
    assert not EMOJI.search(text)


def test_opportunity_formula_matches_core():
    core = (ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "models.py").read_text(
        encoding="utf-8"
    )
    assert "importance + max(importance - satisfaction, 0)" in core  # repo truth guard
    page = (SITE / "index.html").read_text(encoding="utf-8")
    normalized = page.lower().replace("\u2212", "-").replace(" ", "")
    assert "importance+max(importance-satisfaction,0)" in normalized


def test_404_is_self_contained():
    doc = parse("404.html")
    assert doc.lang == "en"
    assert any(lv == 1 for lv, _ in doc.headings)
    assert PAGES_URL in doc.hrefs
    assert not doc.refs, "404.html must not depend on relative assets"
