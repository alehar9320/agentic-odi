"""The site ships two themes: the reader's choice wins, the OS decides the rest."""

from __future__ import annotations

import re

import pytest
from site_support import SITE, all_pages, read_page

THEME_JS = SITE / "assets" / "theme.js"

# Every colour the page paints with, by token name. A theme that forgets one
# leaves that surface on the other theme's palette.
COLOUR_TOKENS = {
    "--bg",
    "--bg-raised",
    "--bg-sunken",
    "--text",
    "--muted",
    "--faint",
    "--accent",
    "--accent-strong",
    "--accent-ink",
    "--green",
    "--amber",
    "--line",
    "--line-strong",
    "--surface",
    "--surface-hover",
    "--glass",
    "--hairline",
    "--shadow-deep",
}


def _block(css: str, selector: str) -> dict[str, str]:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css, re.DOTALL)
    assert match is not None, f"{selector} is missing from the tokens"
    return dict(
        (name.strip(), value.strip().rstrip(";").strip())
        for name, value in (
            line.split(":", 1) for line in match.group(1).splitlines() if ":" in line
        )
    )


def _tokens() -> str:
    return read_page("assets/tokens.css")


def _all_names() -> set[str]:
    return set(re.findall(r"^\s*(--[a-z-]+):", _tokens(), re.MULTILINE))


def test_the_light_theme_overrides_every_colour_token():
    dark = _block(_tokens(), ":root")
    light = _block(_tokens(), ':root[data-theme="light"]')

    missing = COLOUR_TOKENS - set(light)
    assert not missing, f"the light theme leaves these on the dark palette: {sorted(missing)}"
    # A light value for a token the dark theme never defines is a typo.
    unknown = [name for name in light if name not in dark and name not in _all_names()]
    assert not unknown, f"the light theme sets unknown tokens: {sorted(unknown)}"
    assert dark["--bg"] != light["--bg"]


def test_the_light_theme_is_actually_light():
    light = _block(_tokens(), ':root[data-theme="light"]')

    assert light["--bg"] == "#f7f8fb"
    assert light["--text"] == "#12131a"
    assert light["--bg"] != _block(_tokens(), ":root")["--bg"]


@pytest.mark.parametrize("page", all_pages())
def test_every_page_offers_the_theme_toggle(page: str):
    html = read_page(page)

    assert 'class="theme-toggle"' in html
    assert 'aria-label="Switch to the light theme"' in html
    assert "theme-toggle__sun" in html and "theme-toggle__moon" in html


def test_the_theme_is_chosen_before_the_stylesheets_render():
    html = read_page("index.html")

    script = html.index("assets/theme.js")
    tokens = html.index("assets/tokens.css")
    style = html.index("assets/style.css")

    assert script < tokens < style


def test_the_theme_script_defers_to_the_os_and_remembers_the_choice():
    source = THEME_JS.read_text(encoding="utf-8")

    assert "(prefers-color-scheme: light)" in source
    assert "agentic-odi.theme" in source
    assert 'setAttribute("data-theme"' in source


def test_the_toggle_updates_the_switch_in_both_themes():
    source = (SITE / "assets" / "main.js").read_text(encoding="utf-8")

    assert "Switch to the dark theme" in source
    assert "Switch to the light theme" in source
    assert "localStorage.setItem(THEME_KEY" in source
