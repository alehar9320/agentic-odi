"""Odi the Otter — the Agentic ODI mascot.

The single source of truth for every Odi asset: the palette, the golden-ratio
geometry, a small pixel rasterizer, and the renderers that turn a raster into
PNG, SVG, ICO, and terminal art.

The module deliberately has no third-party imports: PNG and ICO are written
with :mod:`struct` and :mod:`zlib` from the standard library, so the art can
be regenerated on any machine with a Python 3.10+ interpreter and nothing
else. Run ``uv run python brand/tools/render.py`` to regenerate every asset.
"""

from __future__ import annotations

import struct
import zlib
from typing import Final

PHI: Final[float] = 1.6180339887
GRID: Final[int] = 32

PALETTE: Final[dict[str, str]] = {
    "ink": "#1B1410",
    "fur": "#B4794C",
    "fur_light": "#DCA871",
    "cream": "#F6EAD8",
    "accent": "#8B8CF8",
    "tile": "#131722",
}

HEAD_W_BUST: Final[int] = 20
HEAD_W_ICON: Final[int] = 22

_Color = str | None
_RGBA = tuple[int, int, int, int]


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert a ``#rrggbb`` string to an ``(r, g, b)`` triple."""
    raw = value.lstrip("#")
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def _relative_luminance(value: str) -> float:
    """Return the WCAG 2.1 relative luminance of a ``#rrggbb`` string."""
    channels = []
    for part in _hex_to_rgb(value):
        srgb = part / 255
        channels.append(srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """Return the WCAG 2.1 contrast ratio between two ``#rrggbb`` colors."""
    first = _relative_luminance(hex_a)
    second = _relative_luminance(hex_b)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


class Raster:
    """A square grid of palette names, or ``None`` for a transparent pixel."""

    def __init__(self, grid: int = GRID) -> None:
        self.grid = grid
        self.px: list[list[_Color]] = [[None] * grid for _ in range(grid)]

    def set(self, x: int, y: int, color: _Color) -> None:
        """Paint one pixel, ignoring coordinates outside the grid."""
        if 0 <= x < self.grid and 0 <= y < self.grid:
            self.px[y][x] = color

    def get(self, x: int, y: int) -> _Color:
        """Return the palette name at a pixel, or ``None`` when transparent."""
        if 0 <= x < self.grid and 0 <= y < self.grid:
            return self.px[y][x]
        return None

    def fill_rect(self, x: int, y: int, w: int, h: int, color: str) -> None:
        """Paint an axis-aligned rectangle of pixels."""
        for row in range(y, y + h):
            for column in range(x, x + w):
                self.set(column, row, color)

    def fill_ellipse(self, cx: float, cy: float, rx: float, ry: float, color: str) -> None:
        """Paint an ellipse centred on a pixel centre."""
        for row in range(self.grid):
            for column in range(self.grid):
                dx = (column + 0.5 - cx) / rx
                dy = (row + 0.5 - cy) / ry
                if dx * dx + dy * dy <= 1.0:
                    self.set(column, row, color)

    def fill_round_rect(self, x: int, y: int, w: int, h: int, r: int, color: str) -> None:
        """Paint a rectangle with circular corners."""
        r = max(0, min(r, w // 2, h // 2))
        for row in range(y, y + h):
            for column in range(x, x + w):
                dx = 0.0
                dy = 0.0
                if column < x + r:
                    dx = x + r - column - 0.5
                elif column >= x + w - r:
                    dx = column - (x + w - r) + 0.5
                if row < y + r:
                    dy = y + r - row - 0.5
                elif row >= y + h - r:
                    dy = row - (y + h - r) + 0.5
                if dx * dx + dy * dy <= r * r:
                    self.set(column, row, color)

    def outline(self, color: str) -> None:
        """Wrap the silhouette in a one-pixel border."""
        filled = [[self.px[y][x] is not None for x in range(self.grid)] for y in range(self.grid)]
        for y in range(self.grid):
            for x in range(self.grid):
                if filled[y][x]:
                    continue
                neighbours = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                touching = any(
                    0 <= nx < self.grid and 0 <= ny < self.grid and filled[ny][nx]
                    for nx, ny in neighbours
                )
                if touching:
                    self.px[y][x] = color

    def composite(self, other: Raster, dx: int = 0, dy: int = 0) -> None:
        """Paint another raster on top of this one."""
        for y in range(other.grid):
            for x in range(other.grid):
                color = other.px[y][x]
                if color is not None:
                    self.set(x + dx, y + dy, color)

    def to_rgba(self) -> list[list[_RGBA]]:
        """Return the grid as a list of rows of ``(r, g, b, a)`` tuples."""
        rows: list[list[_RGBA]] = []
        for y in range(self.grid):
            row: list[_RGBA] = []
            for x in range(self.grid):
                color = self.px[y][x]
                if color is None:
                    row.append((0, 0, 0, 0))
                else:
                    red, green, blue = _hex_to_rgb(PALETTE[color])
                    row.append((red, green, blue, 255))
            rows.append(row)
        return rows


def head_raster(head_w: int, center_y: float | None = None) -> Raster:
    """Draw Odi's head: skull, ears, eyes, muzzle, nose, mouth, and cheeks.

    Every proportion is a power of the golden ratio applied to the head width.
    The head is a golden rectangle (width / height is phi), the eyes sit
    0.618 of the head width apart, and the muzzle is 0.382 of it.
    """
    raster = Raster()
    cx = GRID / 2
    cy = center_y if center_y is not None else (12.0 if head_w <= HEAD_W_BUST else 17.0)
    rx = head_w / 2
    ry = rx / PHI

    ear_r = max(2, round(rx / PHI / 2))
    ear_dx = rx - ear_r * 0.2
    ear_cy = cy - ry + ear_r * 0.1
    for sign in (-1, 1):
        raster.fill_ellipse(cx + sign * ear_dx, ear_cy, ear_r, ear_r, "fur")

    raster.fill_ellipse(cx, cy, rx, ry, "fur")

    cheek_r = max(1.0, rx / 4.5)
    for sign in (-1, 1):
        raster.fill_ellipse(
            cx + sign * rx * 0.66, cy + ry * 0.42, cheek_r, cheek_r * 0.75, "fur_light"
        )

    eye_separation = round(head_w / PHI)
    eye_d = 4 if head_w <= HEAD_W_BUST + 2 else 5
    eye_cy = cy - 0.5
    for sign in (-1, 1):
        ex = round(cx + sign * eye_separation / 2 - eye_d / 2)
        ey = round(eye_cy - eye_d / 2)
        raster.fill_rect(ex, ey, eye_d, eye_d, "ink")
        raster.set(ex + 1, ey + 1, "cream")

    muzzle_w = round(head_w / PHI**2)
    muzzle_h = round(muzzle_w / PHI)
    muzzle_cy = cy + round(ry * 0.5)
    raster.fill_ellipse(cx, muzzle_cy, muzzle_w / 2, muzzle_h / 2, "cream")
    raster.fill_ellipse(
        cx, muzzle_cy - muzzle_h / 2 + 1, muzzle_w / 2 - 1, muzzle_h / 2 - 0.6, "cream"
    )

    nose_w = round(head_w / PHI**3)
    nose_x = round(cx - nose_w / 2)
    nose_y = round(muzzle_cy - muzzle_h / 2) - 1
    raster.set(nose_x + 1, nose_y, "ink")
    raster.set(nose_x + 2, nose_y, "ink")
    raster.fill_rect(nose_x, nose_y + 1, nose_w, 1, "ink")

    mouth_y = nose_y + 4
    raster.fill_rect(round(cx - 1), mouth_y, 3, 1, "ink")

    raster.outline("ink")
    return raster


def mark_raster() -> Raster:
    """Draw the Odi mark: Odi's head on the brand tile."""
    raster = Raster()
    raster.fill_round_rect(0, 0, GRID, GRID, 7, "tile")
    raster.composite(head_raster(HEAD_W_ICON))
    return raster


def bust_raster() -> Raster:
    """Draw the full Odi bust: head, shoulders, chest, and the outcome spark."""
    body = Raster()
    body.fill_ellipse(GRID / 2, 22, 8.5, 6, "fur")
    body.fill_ellipse(GRID / 2, 29, 7, 7, "fur")
    body.fill_round_rect(13, 24, 6, 7, 3, "cream")
    body.outline("ink")

    body.composite(head_raster(HEAD_W_BUST, center_y=12))

    spark_x = round(GRID / 2)
    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        body.set(spark_x + dx, 1 + dy, "accent")
    return body


def _png_bytes(rows: list[list[_RGBA]]) -> bytes:
    """Encode RGBA pixel rows as a PNG byte string."""
    raw = b"".join(b"\x00" + b"".join(struct.pack("4B", *pixel) for pixel in row) for row in rows)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        head = struct.pack(">I", len(payload)) + tag + payload
        return head + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", len(rows[0]), len(rows), 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


_COLOR_PRIORITY: Final[tuple[str, ...]] = ("ink", "fur", "fur_light", "cream", "accent", "tile")


def _majority(pixels: list[_Color]) -> _Color:
    """Pick the dominant color of a block, breaking ties toward the outline."""
    counts: dict[str, int] = {}
    for color in pixels:
        if color is not None:
            counts[color] = counts.get(color, 0) + 1
    if not counts:
        return None
    best = max(
        counts,
        key=lambda color: (
            counts[color],
            -_COLOR_PRIORITY.index(color) if color in _COLOR_PRIORITY else 0,
        ),
    )
    return best


def render_png(raster: Raster, size: int) -> bytes:
    """Render a raster to PNG bytes.

    Sizes larger than the grid are scaled up by nearest neighbour so the pixel
    art stays crisp. Smaller sizes are scaled down by sampling the centre of
    each source block, which keeps the silhouette and the eyes intact and
    stays symmetric, unlike sampling the first pixel of every block.
    """
    source = raster.to_rgba()
    grid = raster.grid
    if size >= grid:
        rows = [
            [source[y * grid // size][x * grid // size] for x in range(size)] for y in range(size)
        ]
    elif grid % size == 0:
        factor = grid // size
        rows = [
            [source[y * factor + factor // 2][x * factor + factor // 2] for x in range(size)]
            for y in range(size)
        ]
    else:
        rows = []
        for oy in range(size):
            row: list[_RGBA] = []
            for ox in range(size):
                block: list[_Color] = []
                for sy in range(
                    oy * grid // size, max(oy * grid // size + 1, (oy + 1) * grid // size)
                ):
                    for sx in range(
                        ox * grid // size, max(ox * grid // size + 1, (ox + 1) * grid // size)
                    ):
                        block.append(raster.get(sx, sy))
                color = _majority(block)
                if color is None:
                    row.append((0, 0, 0, 0))
                else:
                    red, green, blue = _hex_to_rgb(PALETTE[color])
                    row.append((red, green, blue, 255))
            rows.append(row)
    return _png_bytes(rows)


def _rect_elements(raster: Raster, rle: bool) -> str:
    """Return the ``<rect>`` elements for a raster, optionally run-length encoded."""
    parts: list[str] = []
    for y in range(raster.grid):
        x = 0
        while x < raster.grid:
            color = raster.get(x, y)
            if color is None:
                x += 1
                continue
            if not rle:
                parts.append(
                    f'<rect x="{x}" y="{y}" width="1" height="1" fill="{PALETTE[color]}"/>'
                )
                x += 1
                continue
            run = 1
            while x + run < raster.grid and raster.get(x + run, y) == color:
                run += 1
            parts.append(
                f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{PALETTE[color]}"/>'
            )
            x += run
    return "".join(parts)


def svg_rects(raster: Raster, rle: bool = True) -> str:
    """Return only the ``<rect>`` markup for a raster."""
    return _rect_elements(raster, rle)


def _guides(raster: Raster) -> str:
    """Return the golden-ratio guide layer for the bust art."""
    head_w = HEAD_W_BUST
    rx = head_w / 2
    ry = rx / PHI
    cy = 12.0
    eye_separation = round(head_w / PHI)
    muzzle_w = round(head_w / PHI**2)
    muzzle_h = round(muzzle_w / PHI)
    return (
        '<g data-guides="true" fill="none" stroke="#8B8CF8" stroke-width="0.25" opacity="0.85">'
        f'<rect x="{GRID / 2 - rx}" y="{cy - ry}" width="{head_w}" height="{2 * ry}"/>'
        f'<line x1="{GRID / 2 - eye_separation / 2}" y1="{cy - ry}" '
        f'x2="{GRID / 2 + eye_separation / 2}" y2="{cy - ry}"/>'
        f'<rect x="{GRID / 2 - muzzle_w / 2}" y="{cy + round(ry * 0.5) - muzzle_h / 2}" '
        f'width="{muzzle_w}" height="{muzzle_h}"/>'
        "</g>"
    )


def render_svg(raster: Raster, guides: bool = False, rle: bool = False) -> str:
    """Render a raster to an SVG string, one crisp rectangle per pixel."""
    body = _rect_elements(raster, rle=rle)
    if guides:
        body += _guides(raster)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GRID} {GRID}" '
        f'width="{GRID}" height="{GRID}" shape-rendering="crispEdges">'
        f"{body}</svg>"
    )


def render_svg_rle(raster: Raster) -> str:
    """Render a raster to an SVG string with horizontal runs merged."""
    return render_svg(raster, rle=True)


def render_ico(sizes: tuple[int, ...] = (16, 32, 48, 64)) -> bytes:
    """Render an ICO file with PNG-encoded frames at the requested sizes."""
    frames = [(size, render_png(mark_raster(), size)) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = len(header) + 16 * len(frames)
    entries = b""
    payloads = b""
    for size, payload in frames:
        entries += struct.pack(
            "<BBBBHHII",
            size if size < 256 else 0,
            size if size < 256 else 0,
            0,
            0,
            1,
            32,
            len(payload),
            offset,
        )
        payloads += payload
        offset += len(payload)
    return header + entries + payloads


def _banner_cells(raster: Raster) -> list[list[tuple[_Color, _Color]]]:
    """Split a raster into text cells of one pixel wide by two pixels tall."""
    cells: list[list[tuple[_Color, _Color]]] = []
    for row in range(0, raster.grid, 2):
        line: list[tuple[_Color, _Color]] = []
        for column in range(raster.grid):
            top = raster.get(column, row)
            bottom = raster.get(column, row + 1) if row + 1 < raster.grid else None
            line.append((top, bottom))
        cells.append(line)
    return cells


def _ansi_fg(color: _Color) -> str:
    if color is None:
        return "\x1b[39m"
    red, green, blue = _hex_to_rgb(PALETTE[color])
    return f"\x1b[38;2;{red};{green};{blue}m"


def _ansi_bg(color: _Color) -> str:
    if color is None:
        return "\x1b[49m"
    red, green, blue = _hex_to_rgb(PALETTE[color])
    return f"\x1b[48;2;{red};{green};{blue}m"


def ascii_banner(raster: Raster | None = None) -> str:
    """Render the plain half-block banner, one character per two pixels."""
    source = raster if raster is not None else bust_raster()
    lines = []
    for line in _banner_cells(source):
        rendered = "".join("▀" if top or bottom else " " for top, bottom in line)
        lines.append(rendered.rstrip())
    return "\n".join(lines)


def ascii_banner_ansi(raster: Raster | None = None) -> str:
    """Render the 24-bit ANSI half-block banner."""
    source = raster if raster is not None else bust_raster()
    lines = []
    for line in _banner_cells(source):
        parts = []
        for top, bottom in line:
            if top is None and bottom is None:
                parts.append("\x1b[39m\x1b[49m ")
                continue
            parts.append(f"{_ansi_fg(top)}{_ansi_bg(bottom)}▀")
        rendered = "".join(parts)
        lines.append(f"{rendered}\x1b[0m".rstrip() if rendered.strip() else "")
    return "\n".join(lines)
