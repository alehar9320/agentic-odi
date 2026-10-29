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
