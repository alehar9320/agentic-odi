"""Generate the committed social art: website/assets/og.png and favicon.png.

Run from the repo root:

    uv run python website/tools/make_og.py

Output is deterministic - fixed palette, fixed positions, no timestamps, PNG
encoded with compress_level=9 and optimize=True - so website/tests/test_make_og.py
can assert the committed PNGs are pixel-identical to a fresh render.

This module also renders a per-page card for every page the site builds
(:func:`render_site`). The site build calls it, so a page cannot be published
without a card. A card carries the page's own title, its section, and - when the
page states one - a single figure taken from that page's own rendered text. A
page that states no figure gets a card with no number rather than a `0`.
"""

from __future__ import annotations

import argparse
import html as html_module
import io
import re
from pathlib import Path
from typing import NamedTuple

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
    *,
    pill: str = PILL_LABEL,
    figure: str | None = None,
) -> bytes:
    """Render the 1200x630 social card and return its PNG bytes.

    ``pill`` is the label in the top-right chip; ``figure`` is an optional
    accent line under the headline. The defaults reproduce the committed
    ``website/assets/og.png`` byte for byte.
    """
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
    _draw_pill(draw, pill, right=width - MARGIN, cy=middle_y)

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

    if figure is not None:
        figure_font = ImageFont.load_default(size=44)
        y += 18
        draw.text((MARGIN, y), figure, font=figure_font, fill=ACCENT)
        y += round(44 * 1.25)

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


# --------------------------------------------------------------------------
# Per-page cards.
#
# A page's card carries three things: its own title, its section, and - only
# when the page states one in its own rendered text - a single figure. The
# figure is read back out of the page rather than passed in, so the number on
# the card is always a number the page itself makes.

# The count nouns a page may state, in the order a card prefers them. A page
# that states none of these gets a card with no figure rather than a "0".
FIGURE_NOUNS = ("tools", "commands", "connectors", "presets", "guides")

# A count above this is not a count of things on a page; it is a year, a price,
# or an example. Reading one as a figure would be a claim the page never made.
MAX_FIGURE = 999


class PageCard(NamedTuple):
    """The inputs a page's card is rendered from."""

    path: str
    name: str  # file name inside assets/og/, e.g. "docs-mcp.png"
    title: str
    section: str
    description: str
    figure: str | None


def _visible_text(html: str) -> str:
    """A page's rendered text with tags, scripts, styles, and SVG removed.

    A figure must come from what the page says, not from markup that merely
    contains a number (an SVG path, an inline script, a data attribute).
    """
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<svg.*?</svg>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html_module.unescape(text))


def _card_text(value: str) -> str:
    """Text safe to draw: no control characters, single-spaced, trimmed."""
    value = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def figure_for(html: str) -> str | None:
    """The one figure a page states about itself, or ``None``.

    Reads the page's own visible text for ``<count> <noun>``, preferring the
    nouns in :data:`FIGURE_NOUNS` order. A count above :data:`MAX_FIGURE` is
    ignored, so a year or an example number never becomes a claimed figure. A
    stated ``0`` is a real figure and is kept, so a page that genuinely has none
    of a thing is distinguishable from a page that states no figure at all.
    """
    text = _visible_text(html)
    for noun in FIGURE_NOUNS:
        for raw in re.findall(rf"\b(\d[\d,]*)\s+{noun}\b", text):
            value = int(raw.replace(",", ""))
            if 0 <= value <= MAX_FIGURE:
                return f"{value} {noun}"
    return None


def og_name(path: str) -> str:
    """The card's file name inside ``assets/og/`` for a page path.

    ``index.html`` -> ``index.png``, ``docs/mcp/index.html`` -> ``docs-mcp.png``.
    Only ``[a-z0-9-]`` survives, so a nested or duplicated slug can never
    escape the output directory or collide by case.
    """
    stem = path[: -len("index.html")] if path.endswith("index.html") else path
    stem = stem.strip("/")
    if not stem:
        return "index.png"
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") + ".png"


def _meta(html: str, name: str) -> str:
    match = re.search(rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"', html)
    return html_module.unescape(match.group(1)) if match else ""


def _heading(html: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    if match:
        # Strip tags, then resolve entities, so a title like "Roadmap &amp;
        # Next Steps" draws as "Roadmap & Next Steps" rather than the escape.
        text = re.sub(r"<[^>]+>", " ", match.group(1))
        return _card_text(html_module.unescape(text))
    return _card_text(_meta(html, "description"))


def _display_url(pages_url: str) -> str:
    """The URL as a card prints it: host and path, no scheme, no trailing slash."""
    return re.sub(r"^https?://", "", pages_url).rstrip("/")


def page_card(path: str, html: str, section: str) -> PageCard:
    """The card inputs for one built page."""
    title = _heading(html) or WORDMARK
    return PageCard(
        path=path,
        name=og_name(path),
        title=title,
        section=section,
        description=_meta(html, "description"),
        figure=figure_for(html),
    )


def render_page(card: PageCard, pages_url: str) -> bytes:
    """Render one page's card. A card with no figure draws no number."""
    return render(
        headline=card.title,
        subhead=card.description or DEFAULT_SUBHEAD,
        url=_display_url(pages_url),
        pill=card.section,
        figure=card.figure,
    )


def render_site(
    pages: dict[str, str],
    pages_url: str,
    sections: dict[str, str] | None = None,
) -> dict[str, bytes]:
    """One card per built page, keyed by its path under ``assets/``.

    ``pages`` maps a page path (``docs/mcp/index.html``) to its rendered HTML.
    ``sections`` optionally maps a page path to its section label; a page with
    no entry falls back to the first path segment.
    """
    sections = sections or {}
    cards: dict[str, bytes] = {}
    owners: dict[str, str] = {}
    for path, html in sorted(pages.items()):
        section = sections.get(path) or _section_from_path(path)
        card = page_card(path, html, section)
        key = f"assets/og/{card.name}"
        if key in owners:
            raise ValueError(f"two pages share one card path {key}: {owners[key]} and {path}")
        owners[key] = path
        cards[key] = render_page(card, pages_url)
    return cards


def _section_from_path(path: str) -> str:
    """A page's section when the build did not supply one."""
    if path == "index.html":
        return "Overview"
    parts = path.split("/")
    return parts[0].capitalize() if parts else WORDMARK


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


if __name__ == "__main__":
    raise SystemExit(main())
