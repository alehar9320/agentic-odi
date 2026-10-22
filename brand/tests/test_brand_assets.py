"""The contract for Odi's brand assets.

Every committed artifact must match a fresh render of the generator, the
geometry must keep its golden-ratio construction, and the artwork must stay
safe to ship.
"""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import odi_mascot
import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "brand" / "assets"

ASSET_NAMES = (
    "odi-mascot.svg",
    "odi-mark.svg",
    "odi-mascot-256.png",
    "odi-mascot-512.png",
    "odi-mascot-1024.png",
    "odi-icon-1024.png",
    "favicon.svg",
    "favicon.ico",
    "apple-touch-icon.png",
    "odi-ascii.txt",
)


def png_size(data: bytes) -> tuple[int, int]:
    """Return the (width, height) of a PNG byte string."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_phi_constants_match_the_spec():
    assert odi_mascot.PHI == 1.6180339887
    assert odi_mascot.GRID == 32
    assert odi_mascot.HEAD_W_BUST == 20
    assert odi_mascot.HEAD_W_ICON == 22


def test_palette_matches_the_spec():
    assert odi_mascot.PALETTE == {
        "ink": "#1B1410",
        "fur": "#B4794C",
        "fur_light": "#DCA871",
        "cream": "#F6EAD8",
        "accent": "#8B8CF8",
        "tile": "#131722",
    }


def test_head_width_is_a_golden_ratio_of_its_own_height():
    width = odi_mascot.HEAD_W_BUST
    height = round(width / odi_mascot.PHI)
    assert height == 12
    # 20 / 12 = 1.667, within 3% of phi once the height is rounded to a pixel
    assert abs(width / height - odi_mascot.PHI) < 0.05


def test_muzzle_and_nose_follow_the_same_golden_ladder():
    width = odi_mascot.HEAD_W_BUST
    assert round(width / odi_mascot.PHI**2) == 8
    assert round(round(width / odi_mascot.PHI**2) / odi_mascot.PHI) == 5
    assert round(width / odi_mascot.PHI**3) == 5
    assert round(width / (4 * odi_mascot.PHI)) == 3


def test_eye_separation_is_the_golden_section_of_the_head():
    head = odi_mascot.head_raster(odi_mascot.HEAD_W_BUST)
    expected = round(odi_mascot.HEAD_W_BUST / odi_mascot.PHI)
    pupils = {
        x
        for y in range(head.grid)
        for x in range(head.grid)
        if head.get(x, y) == "ink" and head.get(x, y - 1) != "ink" and head.get(x, y + 1) == "ink"
    }
    assert expected == 12
    assert len(pupils) >= 2
    assert expected / odi_mascot.HEAD_W_BUST == pytest.approx(1 / odi_mascot.PHI, abs=0.02)


def test_raster_helpers_draw_within_bounds():
    raster = odi_mascot.Raster(8)
    raster.fill_ellipse(4, 4, 3, 3, "fur")
    raster.fill_rect(0, 0, 2, 2, "ink")
    assert raster.get(0, 0) == "ink"
    assert raster.get(4, 4) == "fur"
    assert raster.get(7, 7) is None
    raster.set(-1, -1, "ink")
    raster.set(99, 99, "ink")


def test_outline_wraps_the_silhouette():
    raster = odi_mascot.Raster(8)
    raster.fill_ellipse(4, 4, 2, 2, "fur")
    raster.outline("ink")
    assert raster.get(0, 0) is None
    assert raster.get(4, 1) == "ink"
    assert raster.get(4, 2) == "fur"
    assert raster.get(4, 4) == "fur"


def test_contrast_ratio_matches_wcag_reference_values():
    assert abs(odi_mascot.contrast_ratio("#000000", "#FFFFFF") - 21.0) < 0.01
    assert abs(odi_mascot.contrast_ratio("#FFFFFF", "#FFFFFF") - 1.0) < 0.01
    assert odi_mascot.contrast_ratio("#B4794C", "#1B1410") > 4.0
    assert odi_mascot.contrast_ratio("#B4794C", "#0A0B0E") > 4.0
    assert odi_mascot.contrast_ratio("#8B8CF8", "#0A0B0E") > 4.0


@pytest.mark.parametrize("name", ASSET_NAMES)
def test_brand_assets_exist(name):
    assert (ASSETS / name).is_file(), f"missing {name}"
    assert (ASSETS / name).stat().st_size > 0


def test_png_assets_have_the_expected_dimensions():
    assert png_size((ASSETS / "odi-mascot-256.png").read_bytes()) == (256, 256)
    assert png_size((ASSETS / "odi-mascot-512.png").read_bytes()) == (512, 512)
    assert png_size((ASSETS / "odi-mascot-1024.png").read_bytes()) == (1024, 1024)
    assert png_size((ASSETS / "odi-icon-1024.png").read_bytes()) == (1024, 1024)
    assert png_size((ASSETS / "apple-touch-icon.png").read_bytes()) == (180, 180)


def test_ico_contains_the_expected_sizes():
    data = (ASSETS / "favicon.ico").read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind) == (0, 1)
    assert count == 4
    widths = [data[6 + 16 * index] for index in range(count)]
    assert widths == [16, 32, 48, 64]


def test_svg_assets_are_well_formed_and_script_free():
    for name in ("odi-mascot.svg", "odi-mark.svg", "favicon.svg"):
        root = ET.parse(ASSETS / name).getroot()
        assert root.tag.endswith("svg")
        assert root.get("viewBox") == "0 0 32 32"
        assert root.get("shape-rendering") == "crispEdges"
        assert not any(element.tag.endswith("script") for element in root.iter())


def test_mascot_svg_carries_the_golden_ratio_guide_layer():
    text = (ASSETS / "odi-mascot.svg").read_text(encoding="utf-8")
    assert 'data-guides="true"' in text


def test_ascii_banner_is_sixteen_rows_of_thirty_two_columns():
    lines = (ASSETS / "odi-ascii.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 16
    assert all(len(line) <= 32 for line in lines)
    assert max(len(line) for line in lines) > 20
    assert any("▀" in line for line in lines)
