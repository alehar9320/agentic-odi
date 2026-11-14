# website/tests/test_make_og.py
import importlib.util
import io
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "website" / "tools"
ASSETS = ROOT / "website" / "assets"


def _load():
    spec = importlib.util.spec_from_file_location("make_og", TOOLS / "make_og.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dims(png: bytes) -> tuple[int, int]:
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    w, h = struct.unpack(">II", png[16:24])  # IHDR: 8 sig + 4 len + 4 type, then width/height
    return w, h


def test_render_is_deterministic_and_sized():
    m = _load()
    a = m.render()
    b = m.render()
    assert _dims(a) == (1200, 630)
    assert a == b


def test_favicon_is_sized():
    m = _load()
    assert _dims(m.render_favicon()) == (32, 32)


def test_cli_writes_both_files_to_out_dir(tmp_path):
    m = _load()
    assert m.main(["--out", str(tmp_path)]) == 0
    assert _dims((tmp_path / "og.png").read_bytes()) == (1200, 630)
    assert _dims((tmp_path / "favicon.png").read_bytes()) == (32, 32)


def test_og_card_uses_the_site_palette():
    m = _load()
    assert m.CANVAS == (10, 11, 14)  # --bg
    assert m.SURFACE == (14, 16, 20)  # --bg-raised
    assert m.TEXT == (241, 242, 244)  # --text
    assert m.ACCENT == (139, 140, 248)  # --accent


def test_the_card_stays_within_ascii():
    # Pillow's built-in font has no em dash, and a missing glyph renders as a
    # tofu box on the card.
    m = _load()
    assert m.DEFAULT_HEADLINE.isascii()
    assert m.DEFAULT_SUBHEAD.isascii()


def test_the_mark_svg_matches_the_favicon_svg():
    mark = (ASSETS / "mark.svg").read_bytes()
    favicon = (ASSETS / "favicon.svg").read_bytes()
    assert mark == favicon


def test_the_mark_svg_uses_the_site_palette():
    mark = (ASSETS / "mark.svg").read_text(encoding="utf-8")
    assert "#8b8cf8" in mark
    assert "#0e1014" in mark


def test_committed_art_matches_generator():
    """Regenerate committed PNGs (uv run python website/tools/make_og.py) whenever the script changes."""
    from PIL import Image

    m = _load()
    fresh = Image.open(io.BytesIO(m.render()))
    committed = Image.open(ASSETS / "og.png")
    assert committed.format == "PNG"
    assert fresh.size == committed.size == (1200, 630)
    assert fresh.tobytes() == committed.tobytes()
    fresh_fav = Image.open(io.BytesIO(m.render_favicon()))
    committed_fav = Image.open(ASSETS / "favicon.png")
    assert fresh_fav.tobytes() == committed_fav.tobytes()


def test_committed_og_size_budget():
    assert (ASSETS / "og.png").stat().st_size < 300_000


# --- per-page cards (ALH-132) ------------------------------------------------


def test_render_card_is_deterministic_and_sized():
    m = _load()
    a = m.render_card("CLI reference", "Build", "24 commands")
    assert _dims(a) == (1200, 630)
    assert a == m.render_card("CLI reference", "Build", "24 commands")


def test_render_card_changes_with_title_section_and_figure():
    m = _load()
    base = m.render_card("CLI reference", "Build", "24 commands")
    assert m.render_card("MCP tool reference", "Build", "24 commands") != base
    assert m.render_card("CLI reference", "Operate", "24 commands") != base
    assert m.render_card("CLI reference", "Build", "31 tools") != base


def test_no_figure_is_absent_rather_than_zero():
    m = _load()
    assert m.render_card("Roadmap", "Operate") == m.render_card("Roadmap", "Operate", None)
    assert m.render_card("Roadmap", "Operate") != m.render_card("Roadmap", "Operate", "0")


def test_a_non_ascii_title_is_drawn_not_dropped():
    m = _load()
    accented = m.render_card("Uppföljning av kaffe", "Build", None)
    assert _dims(accented) == (1200, 630)
    assert accented != m.render_card(
        "Uppföljning av kaffe".encode("ascii", "ignore").decode(), "Build", None
    )


def test_a_dash_is_folded_to_one_the_font_can_draw():
    m = _load()
    hyphen = m.render_card("Ground agents - verified outcomes", "Build", None)
    em = m.render_card("Ground agents \u2014 verified outcomes", "Build", None)
    assert em == hyphen, "an em dash should be drawn as a dash"
    assert em != m.render_card("Ground agents verified outcomes", "Build", None)


def test_the_pill_is_dropped_when_it_repeats_the_wordmark():
    m = _load()
    assert m.card_pill("Build") == "Build"
    assert m.card_pill("Agentic ODI") is None
    assert m.card_pill("") is None
    assert m.render_card("Ground agents", "Agentic ODI") == m.render_card("Ground agents", "")


def test_a_long_title_does_not_crash_generation():
    m = _load()
    long = "Ground agents in verified customer outcomes, jobs, and opportunity scores " * 4
    assert _dims(m.render_card(long, "Get started", "31 tools")) == (1200, 630)


def test_card_names_are_safe_unique_and_inside_the_output_directory():
    m = _load()
    pages = [
        "index.html",
        "docs/index.html",
        "docs/mcp/index.html",
        "docs/cli/index.html",
        "sample/index.html",
        "docs/../../etc/passwd/index.html",
        "docs/utländsk/index.html",
        "mcp/index.html",
    ]
    plan = m.card_names(pages)
    assert len(set(plan.values())) == len(plan), "card names collided"
    for page, card in plan.items():
        assert card.startswith("og/") and card.endswith(".png"), f"{page} -> {card}"
        assert ".." not in card and "/" not in card[3:], (
            f"{page} escapes the card directory: {card}"
        )
        assert card[3:-4].isascii() and card[3:-4].replace("-", "").isalnum(), f"{card} is unsafe"


def test_write_cards_writes_one_png_per_page(tmp_path):
    m = _load()
    pages = [
        {"path": "index.html", "title": "Home", "section": "Product", "figure": "86%"},
        {"path": "docs/mcp/index.html", "title": "MCP tool reference", "section": "Build"},
    ]
    written = m.write_cards(pages, tmp_path)
    assert sorted(written) == ["docs/mcp/index.html", "index.html"]
    for page, path in written.items():
        assert path.is_file(), page
        assert _dims(path.read_bytes()) == (1200, 630)
