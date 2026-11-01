"""Generate the committed sample workspace page: ``website/sample/index.html``.

The sample page shows what the product produces, from a committed fixture,
without installing anything. It is generated, never hand-edited, and it is
self-contained: no external font, script, image, or stylesheet, so it renders
with no network and keeps working when the API is down.

    uv run python website/tools/build_sample.py            # write the page
    uv run python website/tools/build_sample.py --check     # fail if stale

The output is deterministic: every number on the page is read from the fixture,
and the build refuses to publish a numeral the fixture does not contain.
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"
TEMPLATES = SITE / "templates"
FIXTURE = SITE / "content" / "sample-study.json"
OUTPUT = SITE / "sample" / "index.html"

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def environment() -> Environment:
    """The Jinja environment. Autoescape is on, as everywhere in the site."""
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def read_fixture(path: Path = FIXTURE) -> dict[str, Any]:
    """The committed sample fixture, as plain data."""
    return json.loads(path.read_text(encoding="utf-8"))


def _numbers_in(text: str) -> list[str]:
    return _NUMBER.findall(text)


def _visible_numbers(html: str) -> list[str]:
    """Every numeral a reader can see, with markup and inline CSS removed."""
    without_style = re.sub(r"<style\b.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = html_module.unescape(re.sub(r"<[^>]+>", " ", without_style))
    return _numbers_in(text)


def invented_numbers(page: str, fixture: dict[str, Any]) -> list[str]:
    """Numerals the page renders that the fixture does not contain.

    The rule is the application's own: no invented number. A numeral the
    template hardcodes rather than reads from the fixture is reported here.
    """
    allowed = set(_numbers_in(json.dumps(fixture)))
    return sorted({number for number in _visible_numbers(page) if number not in allowed})


def render(fixture: dict[str, Any] | None = None) -> str:
    """Render the sample page from the fixture and return its HTML."""
    fixture = read_fixture() if fixture is None else fixture
    template = environment().get_template("sample.html")
    page = template.render(
        origin=fixture["origin"],
        generated=fixture["generated"],
        job=fixture["job"],
        steps=fixture["steps"],
        outcomes=fixture["outcomes"],
        evidence=fixture["evidence"],
    )

    invented = invented_numbers(page, fixture)
    if invented:
        raise ValueError(
            f"the sample page renders numerals the fixture does not contain: {invented}"
        )
    return page


def write(path: Path = OUTPUT, fixture: dict[str, Any] | None = None) -> Path:
    """Write the rendered sample page to ``path`` and return it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(fixture), encoding="utf-8")
    return path


def check(path: Path = OUTPUT) -> int:
    """Fail if the committed page differs from a fresh render. Write nothing."""
    if not path.is_file():
        print(f"the committed sample page is missing: {path}", file=sys.stderr)
        print("Run: build_sample.py", file=sys.stderr)
        return 1
    if path.read_text(encoding="utf-8") != render():
        print("The committed sample page is out of date. Run: build_sample.py", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUTPUT, help="where to write the page")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if --out differs from a fresh render; write nothing",
    )
    args = parser.parse_args(argv)

    if args.check:
        code = check(args.out)
        if code == 0:
            print(f"The committed sample page is up to date ({args.out}).")
        return code

    written = write(args.out)
    print(f"Wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
