"""Generate the site's social art: the committed og.png and favicon.png, and
one card per page.

Run from the repo root:

    uv run python website/tools/make_og.py

``render_card`` is the per-page shape: a page's own title, its section, and -
only when the page renders one - a single figure. The site build calls it for
every page, so a new page cannot be published without a card.

Output is deterministic - fixed palette, fixed positions, no timestamps, PNG
encoded with compress_level=9 and optimize=True - so website/tests/test_make_og.py
can assert the committed PNGs are pixel-identical to a fresh render.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OG_SIZE = (1200, 630)
FAVICON_SIZE = (32, 32)

DEFAULT_HEADLINE = "Your roadmap is a guess."
# Pillow's built-in font has no em dash, so the card stays ASCII.
DEFAULT_SUBHEAD = "Verified customer outcomes, jobs, and opportunity scores. Served over MCP."
DEFAULT_URL = "alehar9320.github.io/agentic-odi"

# The site's palette, taken from the Living Studio's own theme so the social
# card and the site are the same colour.
CANVAS = (10, 11, 14)  # --bg
SURFACE = (14, 16, 20)  # --bg-raised
TEXT = (241, 242, 244)  # --text
MUTED = (162, 167, 179)  # --muted
FAINT = (113, 118, 127)  # --faint
ACCENT = (139, 140, 248)  # --accent
ACCENT_STRONG = (99, 102, 241)  # --accent-strong
BADGE_FG = (162, 167, 179)  # --muted
BADGE_BG = (24, 24, 32)  # a raised chip on the canvas
HAIRLINE = (38, 42, 52)  # a visible hairline on the canvas

MARGIN = 64
PILL_LABEL = "Experimental"
WORDMARK = "Agentic ODI"
HEADLINE_SIZES = (84, 76, 68, 60, 52)  # shrink until the headline fits two lines

# Mark geometry, normalized inside its bounding box: an ascending two-step
# polyline (flat, riser, flat, riser, flat) ending in a filled apex dot.
_MARK_POINTS = (
    (0.16, 0.78),
    (0.42, 0.78),
    (0.42, 0.53),
    (0.66, 0.53),
    (0.66, 0.28),
    (0.84, 0.28),
)


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    max_width: float,
) -> list[str]:
    """Greedy word wrap measured with draw.textlength."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        elif current:
            lines.append(current)
            current = word
        else:
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_mark(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], line_width: int) -> None:
    x0, y0, x1, y1 = box
    width = x1 - x0 + 1
    height = y1 - y0 + 1
    draw.rounded_rectangle(box, radius=max(2, width // 4), fill=SURFACE, outline=HAIRLINE, width=1)
    points = [(x0 + px * (width - 1), y0 + py * (height - 1)) for px, py in _MARK_POINTS]
    draw.line(points, fill=ACCENT, width=line_width, joint="curve")
    apex_x, apex_y = points[-1]
    radius = max(2, round(width * 0.09))
    draw.ellipse(
        (apex_x - radius, apex_y - radius, apex_x + radius, apex_y + radius),
        fill=ACCENT,
    )


def _draw_pill(draw: ImageDraw.ImageDraw, label: str, right: int, cy: int) -> None:
    font = ImageFont.load_default(size=22)
    pad_x = 20
    height = 44
    width = round(draw.textlength(label, font=font)) + 2 * pad_x
    x1, y0 = right, cy - height // 2
    x0, y1 = x1 - width, y0 + height
    draw.rounded_rectangle((x0, y0, x1, y1), radius=height // 2, fill=BADGE_BG)
    draw.text(((x0 + x1) / 2, cy), label, font=font, fill=BADGE_FG, anchor="mm")


def _wash(
    size: tuple[int, int],
    color: tuple[int, int, int],
    center: tuple[float, float],
    radius: float,
    strength: int,
) -> tuple[Image.Image, Image.Image, tuple[int, int]]:
    """A soft radial wash, drawn small and scaled up.

    The site's canvas carries two of these. Reproducing them keeps the social
    card looking like the page it links to.
    """
    small = 180
    mask = Image.new("L", (small, small), 0)
    painter = ImageDraw.Draw(mask)
    steps = 48
    for step in range(steps, 0, -1):
        fraction = step / steps
        extent = small * radius * fraction
        value = int(strength * (1 - fraction))
        painter.ellipse(
            (
                small / 2 - extent,
                small / 2 - extent,
                small / 2 + extent,
                small / 2 + extent,
            ),
            fill=value,
        )
    mask = mask.resize(size, Image.Resampling.LANCZOS)
    layer = Image.new("RGB", size, color)
    offset = (
        int(center[0] * size[0] - small * radius / 2),
        int(center[1] * size[1] - small * radius / 2),
    )
    return layer, mask, offset


def _to_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=9, optimize=True)
    return buffer.getvalue()


def render(
    headline: str = DEFAULT_HEADLINE,
    subhead: str = DEFAULT_SUBHEAD,
    url: str = DEFAULT_URL,
) -> bytes:
    """Render the 1200x630 social card and return its PNG bytes."""
    width, height = OG_SIZE
    image = Image.new("RGB", OG_SIZE, CANVAS)

    # The site's two canvas washes, in the same places.
    for color, center, radius, strength in (
        (ACCENT_STRONG, (0.50, 1.08), 0.62, 26),
        (ACCENT_STRONG, (0.68, -0.12), 0.72, 22),
    ):
        layer, mask, offset = _wash(OG_SIZE, color, center, radius, strength)
        image.paste(layer, offset, mask)

    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((24, 24, width - 25, height - 25), radius=28, outline=HAIRLINE, width=1)

    mark_size = 44
    _draw_mark(draw, (MARGIN, MARGIN, MARGIN + mark_size - 1, MARGIN + mark_size - 1), 3)
    middle_y = MARGIN + mark_size // 2
    draw.text(
        (MARGIN + mark_size + 16, middle_y),
        WORDMARK,
        font=ImageFont.load_default(size=30),
        fill=TEXT,
        anchor="lm",
    )
    _draw_pill(draw, PILL_LABEL, right=width - MARGIN, cy=middle_y)

    text_width = width - 2 * MARGIN
    size = HEADLINE_SIZES[0]
    font = ImageFont.load_default(size=size)
    headline_lines = _wrap(draw, headline, font, text_width)
    for size in HEADLINE_SIZES[1:]:
        if len(headline_lines) <= 2:
            break
        font = ImageFont.load_default(size=size)
        headline_lines = _wrap(draw, headline, font, text_width)

    y = 200
    for line in headline_lines[:2]:
        draw.text((MARGIN, y), line, font=font, fill=TEXT)
        y += round(size * 1.25)

    subhead_font = ImageFont.load_default(size=28)
    y += 26
    for line in _wrap(draw, subhead, subhead_font, text_width):
        draw.text((MARGIN, y), line, font=subhead_font, fill=MUTED)
        y += 36

    draw.text(
        (MARGIN, height - MARGIN),
        url,
        font=ImageFont.load_default(size=26),
        fill=MUTED,
        anchor="ld",
    )
    return _to_png(image)


def render_favicon() -> bytes:
    """Render the 32x32 favicon tile (canvas + mark only) as PNG bytes."""
    image = Image.new("RGB", FAVICON_SIZE, CANVAS)
    draw = ImageDraw.Draw(image)
    _draw_mark(draw, (2, 2, 29, 29), 2)
    return _to_png(image)


def write(out_dir: Path) -> list[Path]:
    """Write og.png and favicon.png into out_dir and return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    og_path = out_dir / "og.png"
    favicon_path = out_dir / "favicon.png"
    og_path.write_bytes(render())
    favicon_path.write_bytes(render_favicon())
    return [og_path, favicon_path]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the site's og.png and favicon.png.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets",
        help="directory to write og.png and favicon.png into (default: website/assets)",
    )
    args = parser.parse_args(argv)
    for path in write(args.out):
        print(f"wrote {path}")
    return 0


# --- one card per page -------------------------------------------------------

CARD_TITLE_SIZES = (72, 64, 56, 48, 42)
CARD_TITLE_LINES = 3
CARD_TITLE_Y = 196
CARD_FIGURE_Y = 440
CARD_STEM_MAX = 80

# Punctuation the built-in font has no glyph for, mapped to the ASCII it stands
# for. Dropping these would run words together, which changes what a title says.
_CARD_PUNCT = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\u00b7": "-",
        "\u2022": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2039": "'",
        "\u203a": "'",
        "\u2026": "...",
        "\u2192": "->",
        "\u00a9": "(c)",
        "\u00ae": "(r)",
        "\u2122": "TM",
        "\u00a0": " ",
        "\u2007": " ",
        "\u2009": " ",
        "\u200a": " ",
        "\u202f": " ",
        "\u200b": "",
    }
)


def _card_text(value: str) -> str:
    """Fold a page's own text into what the built-in font can draw.

    Pillow's scalable default has no non-ASCII glyphs, so an accented letter
    would render as a tofu box. NFKD first keeps the letter and drops the mark:
    the card reads as the page reads. Punctuation the font lacks is mapped to
    the ASCII it stands for rather than dropped, so a dash keeps its words
    apart. A title with nothing left falls back to the wordmark.
    """
    folded = unicodedata.normalize("NFKD", value.translate(_CARD_PUNCT))
    return " ".join(folded.encode("ascii", "ignore").decode().split()) or WORDMARK


def card_pill(section: str) -> str | None:
    """The section label to draw, or ``None`` when it would add nothing.

    The landing page's section is the site itself, and the wordmark is already
    on the card; repeating it as a label says nothing a reader cannot see.
    """
    label = _card_text(section) if section.strip() else ""
    return label if label and label != WORDMARK else None


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """The site canvas: both washes and the hairline frame."""
    width, height = OG_SIZE
    image = Image.new("RGB", OG_SIZE, CANVAS)
    for color, center, radius, strength in (
        (ACCENT_STRONG, (0.50, 1.08), 0.62, 26),
        (ACCENT_STRONG, (0.68, -0.12), 0.72, 22),
    ):
        layer, mask, offset = _wash(OG_SIZE, color, center, radius, strength)
        image.paste(layer, offset, mask)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, width - 25, height - 25), radius=28, outline=HAIRLINE, width=1)
    return image, draw


def render_card(title: str, section: str, figure: str | None = None) -> bytes:
    """Render one page's 1200x630 card: its title, its section, its own figure.

    ``figure`` is a number the page itself displays. Leaving it out draws the
    section card with no number at all - a missing figure is not a zero.
    """
    width, height = OG_SIZE
    image, draw = _canvas()

    mark_size = 44
    _draw_mark(draw, (MARGIN, MARGIN, MARGIN + mark_size - 1, MARGIN + mark_size - 1), 3)
    middle_y = MARGIN + mark_size // 2
    draw.text(
        (MARGIN + mark_size + 16, middle_y),
        WORDMARK,
        font=ImageFont.load_default(size=30),
        fill=TEXT,
        anchor="lm",
    )
    pill = card_pill(section)
    if pill:
        _draw_pill(draw, pill, right=width - MARGIN, cy=middle_y)

    text_width = width - 2 * MARGIN
    folded_title = _card_text(title)
    for size in CARD_TITLE_SIZES:
        font = ImageFont.load_default(size=size)
        lines = _wrap(draw, folded_title, font, text_width)
        if len(lines) <= CARD_TITLE_LINES or size == CARD_TITLE_SIZES[-1]:
            break
    y = CARD_TITLE_Y
    for line in lines[:CARD_TITLE_LINES]:
        draw.text((MARGIN, y), line, font=font, fill=TEXT)
        y += round(size * 1.22)

    if figure:
        draw.text(
            (MARGIN, CARD_FIGURE_Y),
            _card_text(figure),
            font=ImageFont.load_default(size=58),
            fill=ACCENT,
        )

    draw.text(
        (MARGIN, height - MARGIN),
        DEFAULT_URL,
        font=ImageFont.load_default(size=26),
        fill=MUTED,
        anchor="ld",
    )
    return _to_png(image)


def _card_stem(page_path: str) -> str:
    """A page's card name: its whole path, folded into one safe slug."""
    stem = page_path[: -len("index.html")] if page_path.endswith("index.html") else page_path
    stem = stem.rstrip("/")
    folded = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-") or "home"
    if len(slug) > CARD_STEM_MAX:
        digest = hashlib.sha256(stem.encode("utf-8")).hexdigest()[:8]
        slug = f"{slug[:CARD_STEM_MAX]}-{digest}"
    return slug


def card_names(page_paths: list[str]) -> dict[str, str]:
    """Map every page path to its card path, one file per page, no collisions.

    The whole page path feeds the name, so ``docs/mcp/`` and ``mcp/`` cannot
    land on the same file; a fold that still collides gets a numeric suffix in
    path order, which keeps the mapping reproducible.
    """
    names: dict[str, str] = {}
    used: set[str] = set()
    for page in sorted(page_paths):
        stem = _card_stem(page)
        candidate = stem
        suffix = 2
        while candidate in used:
            candidate = f"{stem}-{suffix}"
            suffix += 1
        used.add(candidate)
        names[page] = f"og/{candidate}.png"
    return names


def write_cards(pages: list[dict], out_dir: Path) -> dict[str, Path]:
    """Write one card per page into ``out_dir`` and return page path -> file."""
    names = card_names([page["path"] for page in pages])
    written: dict[str, Path] = {}
    for page in pages:
        target = out_dir / names[page["path"]]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(render_card(page["title"], page["section"], page.get("figure")))
        written[page["path"]] = target
    return written


if __name__ == "__main__":
    raise SystemExit(main())
