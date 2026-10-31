"""Publish a read-only sample workspace on the site.

The page is generated from a committed fixture,
``website/content/sample-study.json``, which is itself derived from the demo
loader's fixture in ``apps/studio-api`` and relabelled ``origin="sample"``. One
corpus, two presentations: the local demo and this page. There is no second
corpus to drift.

    python website/tools/build_sample.py            # write the committed page
    python website/tools/build_sample.py --check    # fail if it drifted

Nothing here talks to a network, and the output carries no client JavaScript:
it is one self-contained HTML file with inlined CSS and data. The build refuses
to emit a page that invents a number or drops a row's sample marker.
"""

from __future__ import annotations

import argparse
import html as html_module
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import build_site
import extract

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"
CONTENT = SITE / "content"
FIXTURE = CONTENT / "sample-study.json"
OUT_DIR = SITE

SEED_PY = ROOT / "apps" / "studio-api" / "src" / "agentic_odi_studio_api" / "studio" / "seed.py"
STUDIO_THEME = ROOT / "apps" / "studio" / "src" / "styles" / "theme.css"

ORIGIN = "sample"
#: The fixture records when it was generated. It is a fixture value on purpose:
#: rendering stays byte-for-byte reproducible, so the drift check can compare a
#: fresh render with the committed page without the calendar moving underneath it.
DEFAULT_GENERATED = "2026-10-31"

PAGE_TITLE = "Sample workspace — Agentic ODI"
PAGE_DESCRIPTION = (
    "A read-only sample workspace: one job, its steps, its scored outcomes, "
    "and the evidence behind them. Every row is a sample."
)

_JOB_FIELDS = ("id", "name", "description")
_STEP_FIELDS = ("id", "job_id", "name", "order")
_OUTCOME_FIELDS = ("id", "job_id", "statement", "importance", "satisfaction", "opportunity_score")
_EVIDENCE_FIELDS = (
    "id",
    "source_name",
    "source_kind",
    "name",
    "content",
    "url",
    "job_id",
    "outcome_id",
)


def _seed_payload() -> dict[str, Any]:
    """The demo loader's fixture, loaded from its own module.

    The seed module is a pure data module with no package-relative imports, so
    it is loaded by path rather than imported. That keeps this build honest
    about *where* the sample comes from: it reads the demo fixture instead of
    authoring a second corpus.
    """
    spec = importlib.util.spec_from_file_location("agentic_odi_demo_seed", SEED_PY)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load the demo fixture from {SEED_PY}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload: dict[str, Any] = module.seed_payload()
    return payload


def _pick(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """The named fields of a fixture row, with the sample origin added.

    Reading by name is the point: the demo seed carries ``evidence`` and
    ``telemetry`` keys that are not fields of the Outcome model, and those are
    exactly the fabricated values that must not reach the page. A missing field
    is an error, not a blank.
    """
    picked = {field: row[field] for field in fields}
    picked["origin"] = ORIGIN
    return picked


def build_fixture(*, generated: str = DEFAULT_GENERATED) -> dict[str, Any]:
    """The sample study, derived from the demo fixture and relabelled."""
    seed = _seed_payload()
    jobs = seed["jobs"]
    if len(jobs) != 1:
        raise ValueError("the demo fixture must carry exactly one job")
    return {
        "label": "Sample workspace",
        "notice": (
            "Every row below is a sample. It came from a committed fixture, not "
            "from a connector, and it is not anyone's research."
        ),
        "origin": ORIGIN,
        "generated": generated,
        "job": _pick(jobs[0], _JOB_FIELDS),
        "steps": [_pick(step, _STEP_FIELDS) for step in seed["steps"]],
        "outcomes": [_pick(outcome, _OUTCOME_FIELDS) for outcome in seed["outcomes"]],
        "evidence": [_pick(item, _EVIDENCE_FIELDS) for item in seed["evidence"]],
    }


def fixture_bytes(fixture: dict[str, Any]) -> bytes:
    """The fixture as committed JSON: stable, readable, one trailing newline."""
    return (json.dumps(fixture, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def read_fixture(path: Path = FIXTURE) -> dict[str, Any]:
    """The committed fixture."""
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _tokens_css() -> str:
    """The Studio palette, inlined so the page needs no stylesheet request."""
    tokens = extract.read_tokens(STUDIO_THEME)
    body = "\n".join(f"  {name}: {value};" for name, value in tokens.items())
    return f":root {{\n{body}\n}}"


def render(fixture: dict[str, Any]) -> str:
    """The page, rendered from the fixture and checked before it is returned."""
    env = build_site.environment()
    counts = {
        "jobs": 1,
        "steps": len(fixture["steps"]),
        "outcomes": len(fixture["outcomes"]),
        "evidence": len(fixture["evidence"]),
    }
    html = env.get_template("sample.html").render(
        title=PAGE_TITLE,
        description=PAGE_DESCRIPTION,
        tokens_css=_tokens_css(),
        fixture=fixture,
        counts=counts,
    )
    check_rows(html, fixture)
    check_numerals(html, fixture)
    return html


def page_numerals(html: str) -> list[str]:
    """Every numeral a reader sees, with scripts, styles, tags, and entities resolved."""
    without_blocks = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = html_module.unescape(re.sub(r"<[^>]+>", "", without_blocks))
    return re.findall(r"\d+(?:\.\d+)?", text)


def fixture_numerals(fixture: dict[str, Any]) -> set[str]:
    """Every numeral the fixture contains, plus the counts the page states."""
    numbers = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(fixture, ensure_ascii=False)))
    numbers.add(str(len(fixture["steps"])))
    numbers.add(str(len(fixture["outcomes"])))
    numbers.add(str(len(fixture["evidence"])))
    numbers.add("1")  # the job count
    return numbers


def chrome_numerals(fixture: dict[str, Any]) -> set[str]:
    """The numerals the page's own chrome states: only the generation date."""
    return set(re.findall(r"\d+", str(fixture["generated"])))


def check_numerals(html: str, fixture: dict[str, Any]) -> None:
    """Fail if the page renders a numeral the fixture does not contain."""
    allowed = fixture_numerals(fixture) | chrome_numerals(fixture)
    stray = sorted({number for number in page_numerals(html) if number not in allowed})
    if stray:
        raise ValueError(f"the sample page renders numerals absent from the fixture: {stray}")


def check_rows(html: str, fixture: dict[str, Any]) -> None:
    """Fail if any data row is missing, or renders without its sample marker."""
    expected = 1 + len(fixture["steps"]) + len(fixture["outcomes"]) + len(fixture["evidence"])
    bodies = re.findall(r"<tbody\b[^>]*>(.*?)</tbody>", html, re.DOTALL)
    rows = [row for body in bodies for row in re.findall(r"<tr\b[^>]*>", body)]
    if len(rows) != expected:
        raise ValueError(f"the sample page renders {len(rows)} data rows, expected {expected}")
    for row in rows:
        if f'data-origin="{ORIGIN}"' not in row:
            raise ValueError(f"a sample row is missing its marker: {row}")


def _existing_generated() -> str | None:
    """The generation date already recorded in the committed fixture, if any."""
    if not FIXTURE.is_file():
        return None
    value = read_fixture().get("generated")
    return str(value) if value else None


def build(out_dir: Path = OUT_DIR, *, check: bool = False, generated: str | None = None) -> int:
    """Write the fixture and the page, or check them for drift.

    With ``check=True`` nothing is written: the committed files are compared
    against a fresh render and the process exits non-zero when they differ.
    """
    out_dir = Path(out_dir)
    date_value = generated or _existing_generated() or DEFAULT_GENERATED
    fixture = build_fixture(generated=date_value)
    files: dict[str, bytes] = {
        "content/sample-study.json": fixture_bytes(fixture),
        "sample/index.html": render(fixture).encode("utf-8"),
    }

    if check:
        stale = sorted(
            name
            for name, data in files.items()
            if not (out_dir / name).is_file() or (out_dir / name).read_bytes() != data
        )
        if stale:
            print("The sample workspace is out of date. Run: build_sample.py", file=sys.stderr)
            for name in stale:
                print(f"  {name}", file=sys.stderr)
            raise SystemExit(1)
        return len(files)

    for name, data in files.items():
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="where to write the sample")
    parser.add_argument(
        "--generated",
        default=None,
        help="the generation date to record (default: keep the committed one)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed sample differs from a fresh render; write nothing",
    )
    args = parser.parse_args(argv)

    if args.check:
        count = build(args.out, check=True)
        print(f"The sample workspace is up to date ({count} files).")
        return 0

    count = build(args.out, generated=args.generated)
    print(f"Built the sample workspace ({count} files) into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
