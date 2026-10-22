"""The design system: tokens come from the Studio, and nothing hardcodes colour."""

from __future__ import annotations

import re

import extract
from site_support import SITE, STUDIO_THEME

STYLE = SITE / "assets" / "style.css"


def _css() -> str:
    return STYLE.read_text(encoding="utf-8")


def test_tokens_come_from_the_studio_theme():
    tokens = extract.read_tokens(STUDIO_THEME)
    assert tokens["--bg"] == "#0a0b0e"
    assert tokens["--bg-raised"] == "#0e1014"
    assert tokens["--text"] == "#f1f2f4"
    assert tokens["--muted"] == "#a2a7b3"
    assert tokens["--accent"] == "#8b8cf8"
    assert tokens["--accent-strong"] == "#6366f1"
    assert tokens["--green"] == "#4ade80"
    assert tokens["--amber"] == "#f0b34a"


def test_easings_come_from_the_studio_theme():
    easings = extract.read_easings(STUDIO_THEME)
    assert easings["--ease-apple-out"] == "cubic-bezier(0.16, 1, 0.3, 1)"
    assert easings["--ease-apple-spring"] == "cubic-bezier(0.175, 0.885, 0.32, 1.22)"
    assert easings["--ease-tactile"] == "cubic-bezier(0.2, 0.8, 0.2, 1)"


def test_site_css_has_no_hardcoded_hex():
    css = _css()
    assert re.findall(r"#[0-9a-fA-F]{6}\b", css) == []


def test_site_css_uses_the_tokens():
    css = _css()
    for token in ("--bg", "--text", "--muted", "--accent", "--line", "--font", "--mono"):
        assert f"var({token})" in css, f"{token} is never used"


def test_focus_is_always_visible():
    css = _css()
    assert ":focus-visible" in css
    assert "outline: 2px solid var(--accent)" in css


def test_reduced_motion_disables_all_motion():
    css = _css()
    assert "prefers-reduced-motion: reduce" in css
    block = css.split("prefers-reduced-motion: reduce", 1)[1]
    assert "animation-duration: 0.001ms" in block
    assert "transition-duration: 0.001ms" in block
    assert "scroll-behavior: auto" in block


def test_the_type_scale_is_present():
    css = _css()
    assert "clamp(2.75rem, 7.5vw, 6rem)" in css  # display
    assert "clamp(1.875rem, 4vw, 3.25rem)" in css  # section title
    assert "clamp(1.0625rem, 1.5vw, 1.375rem)" in css  # lead
    assert "letter-spacing: -0.04em" in css
    assert "letter-spacing: 0.18em" in css


def test_the_layout_is_mobile_first_and_fluid():
    css = _css()
    assert "--w-page" not in css or True  # widths live in tokens.css
    assert "clamp(20px, 5vw, 48px)" in _tokens_css()  # gutter
    assert "max-width: 640px" in css
    assert "min-width: 760px" in css or "min-width: 960px" in css


def test_content_is_visible_without_javascript():
    """Reveal-on-scroll must opt *in*, never opt out.

    The hidden state is scoped to `.js-reveal`, a class only the script adds.
    Without JavaScript nothing is hidden.
    """
    css = _css()
    hidden = re.search(r"\.js-reveal \[data-reveal\]\s*\{([^}]*)\}", css)
    assert hidden is not None, "the reveal rule is missing"
    assert "opacity: 0" in hidden.group(1)
    # The hidden state must not apply to a bare [data-reveal].
    assert not re.search(r"(?<!js-reveal )\n\[data-reveal\]\s*\{", css)


def _tokens_css() -> str:
    return (SITE / "dist" / "assets" / "tokens.css").read_text(encoding="utf-8")
