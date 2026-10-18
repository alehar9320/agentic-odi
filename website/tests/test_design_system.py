"""Design system tests for colors, typography, spacing, grid, motion, and focus-visible."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"
CSS_PATH = SITE / "assets" / "style.css"


def _read_css():
    return CSS_PATH.read_text(encoding="utf-8")


def _find_rule(css, selector):
    """Find a CSS rule block by selector, returning its content."""
    # Match regular rules :sel{...}
    patterns = [
        rf"{re.escape(selector)}\s*\{{(.*?)\}}",
    ]
    # Match :root inside @media (prefers-color-scheme: dark) { :root { ... } }
    if selector == ":root":
        patterns.append(r"@media\s+\(prefers-color-scheme:\s*dark\)\s*\{.*?:root\s*\{(.*?)\}}")
    for pat in patterns:
        m = re.search(pat, css, re.DOTALL)
        if m:
            return m.group(1)
    return None


def _has_decl(css_block, prop, val):
    """Check if a CSS decl block contains prop: val (allowing whitespace)."""
    return bool(re.search(rf"{re.escape(prop)}\s*:\s*{re.escape(val)}", css_block))


class TestColorPalette:
    """Verify exact color tokens from the design spec."""

    def test_color_tokens_defined_in_root(self):
        css = _read_css()
        root = _find_rule(css, ":root")
        assert root is not None, ":root rule not found"

        tokens = {
            "--color-bg-light": "#f8f9fa",
            "--color-bg-dark": "#212b36",
            "--color-fg-light": "#212b36",
            "--color-fg-dark": "#f8f9fa",
            "--color-accent": "#3b82f6",
            "--color-accent-hover": "#2563eb",
            "--color-contrast": "#334155",
            "--color-reduced-motion": "#e5e7eb",
        }
        for token, val in tokens.items():
            assert _has_decl(root, token, val), f"Missing token: {token}: {val}"

    def test_dark_mode_overrides(self):
        css = _read_css()
        dark = _find_rule(css, "@media (prefers-color-scheme: dark)")
        assert dark is not None, "Dark mode media query not found"

        dark_tokens = {
            "--color-bg-light": "#212b36",
            "--color-bg-dark": "#f8f9fa",
            "--color-fg-light": "#f8f9fa",
            "--color-fg-dark": "#212b36",
        }
        for token, val in dark_tokens.items():
            assert _has_decl(dark, token, val), f"Missing dark token: {token}: {val}"


class TestTypography:
    """Verify typography clamp values and base styles."""

    def test_base_font_size_and_line_height(self):
        css = _read_css()
        assert "font-size:1rem" in css, "Base font-size should be 1rem"
        assert "line-height:1.5" in css, "Base line-height should be 1.5"

    def test_h1_clamp_value(self):
        css = _read_css()
        assert "clamp(1.5rem,3vw,3rem)" in css, "h1 should use clamp(1.5rem,3vw,3rem)"

    def test_h2_clamp_value(self):
        css = _read_css()
        assert "clamp(1.25rem,2vw,2rem)" in css, "h2 should use clamp(1.25rem,2vw,2rem)"

    def test_text_max_width(self):
        css = _read_css()
        assert "max-width:64ch" in css, "Text blocks should have max-width: 64ch"


class TestFocusVisible:
    """Verify focus-visible rules."""

    def test_focus_visible_rule(self):
        css = _read_css()
        assert "*:focus-visible" in css, "*:focus-visible rule should exist"
        assert "outline" in css, "outline property should be set for focus-visible"
        assert "var(--color-accent)" in css, "focus-visible should use var(--color-accent)"


class TestMotion:
    """Verify motion/transition rules."""

    def test_default_transition(self):
        css = _read_css()
        assert "transition:all 200ms ease-in-out" in css, (
            "Default transition should be 200ms ease-in-out"
        )

    def test_reduced_motion_media_query(self):
        css = _read_css()
        assert "@media (prefers-reduced-motion: reduce)" in css, (
            "Reduced motion media query should exist"
        )
        assert "transition:none" in css, "Reduced motion should disable transitions"


class TestGridAndSpacing:
    """Verify grid and spacing system."""

    def test_grid_layout_640px(self):
        css = _read_css()
        assert "@media (min-width:640px)" in css, "640px breakpoint should exist"
        assert "minmax(250px,1fr)" in css, "Grid should use minmax(250px,1fr)"

    def test_spacing_scale_unit(self):
        css = _read_css()
        # Check that 0.25rem unit is used in spacing scale
        assert ".25rem" in css or "0.25rem" in css, "Spacing should use 0.25rem unit"

    def test_max_width_64ch(self):
        css = _read_css()
        assert "max-width:64ch" in css, "Main content max-width should be 64ch"
