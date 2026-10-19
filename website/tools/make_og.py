"""Generate the committed social art: website/assets/og.png and favicon.png.

Run from the repo root:

    uv run python website/tools/make_og.py

Output is deterministic - fixed palette, fixed positions, no timestamps, PNG
encoded with compress_level=9 and optimize=True - so website/tests/test_make_og.py
can assert the committed PNGs are pixel-identical to a fresh render.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OG_SIZE = (1200, 630)
FAVICON_SIZE = (32, 32)

DEFAULT_HEADLINE = "Your roadmap is a guess."
DEFAULT_SUBHEAD = "Verified customer outcomes, jobs, and opportunity scores — served over MCP."
DEFAULT_URL = "alehar9320.github.io/agentic-odi"

CANVAS = (11, 13, 19)  # #0b0d13
SURFACE = (19, 23, 34)  # #131722
TEXT = (241, 245, 249)  # #f1f5f9
MUTED = (148, 163, 184)  # #94a3b8
ACCENT = (64, 156, 255)  # #409cff
BADGE_FG = (203, 213, 225)  # #cbd5e1
BADGE_BG = (30, 41, 59)  # #1e293b
HAIRLINE = (51, 65, 85)  # #334155

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


if __name__ == "__main__":
    raise SystemExit(main())
