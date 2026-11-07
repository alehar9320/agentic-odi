"""The eight-stage guide must survive being followed, not just being read.

``docs/cli.md`` is a reference, so it is checked for command *names*. ``docs/method.md``
is a sequence a person follows with a terminal open, so a name is not enough — the whole
sequence has to execute. This test runs every fenced command against a throwaway SQLite
store, in the order the guide gives them, and resolves the ``$JOB_ID`` and friends the
guide refers to from the ids its own earlier commands printed. A command that does not
exist, or a placeholder no earlier command created, fails here rather than in someone's
meeting.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

import pytest
from agentic_odi_cli.cli import app
from agentic_odi_core import JOB_STAGE_ORDER, JobStage
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "method.md"

#: The fixed shape every stage section carries. A guide with eight different shapes is a
#: blog series, so the subheadings are part of the contract.
BLOCKS = (
    "What you are trying to learn",
    "What good looks like",
    "The mistakes",
    "Do it here",
    "How you know you are done",
)

#: Which placeholder each command group creates.
_CREATORS = {
    "jobs": "JOB_ID",
    "steps": "STEP_ID",
    "desired-outcomes": "OUTCOME_ID",
    "evidence": "EVIDENCE_ID",
    "segments": "SEGMENT_ID",
}

BASH_BLOCK = re.compile(r"^```bash\n(?P<body>.*?)^```", re.DOTALL | re.MULTILINE)
HEADING = re.compile(r"^(?P<hashes>#{2,3}) (?P<title>.*?)\s*$", re.MULTILINE)
LIST_ITEM = re.compile(r"^- (?P<text>.*)$", re.MULTILINE)
LINK = re.compile(r"\]\((?P<target>[^)\s]+)\)")
ENTRY_PREFIXES = ("agentic-odi", "odi", "uv run agentic-odi")
UNSUPPORTED = "**Not in the product yet:**"


@pytest.fixture(scope="module")
def guide() -> str:
    assert GUIDE.exists(), "docs/method.md is missing"
    return GUIDE.read_text(encoding="utf-8")


def stage_title(stage: JobStage) -> str:
    return stage.value.capitalize()


def _section_body(text: str, stage: JobStage) -> str:
    heading = f"## {stage_title(stage)}"
    start = text.find(heading)
    assert start != -1, f"docs/method.md has no '{heading}' section"
    rest = text[start + len(heading) :]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _block_body(section: str, block: str) -> str:
    start = section.find(f"### {block}")
    assert start != -1, f"'### {block}' block is missing"
    rest = section[start + len(f"### {block}") :]
    end = rest.find("\n### ")
    return rest if end == -1 else rest[:end]


def _headings(text: str, level: str) -> list[str]:
    return [
        match.group("title") for match in HEADING.finditer(text) if match.group("hashes") == level
    ]


def test_the_eight_stages_are_the_job_map_stages_in_order(guide: str) -> None:
    expected = [stage_title(stage) for stage in JOB_STAGE_ORDER]
    found = [title for title in _headings(guide, "##") if title in expected]
    assert found == expected, (
        "the guide must carry exactly one section per Universal Job Map stage, in canonical "
        f"order; found {found}"
    )


@pytest.mark.parametrize("stage", list(JOB_STAGE_ORDER), ids=lambda stage: stage.value)
def test_each_stage_carries_the_fixed_shape(guide: str, stage: JobStage) -> None:
    found = _headings(_section_body(guide, stage), "###")
    assert found == list(BLOCKS), f"{stage.value}: blocks are {found}, not the fixed shape"


@pytest.mark.parametrize("stage", list(JOB_STAGE_ORDER), ids=lambda stage: stage.value)
def test_every_stage_names_three_mistakes_with_their_symptom(guide: str, stage: JobStage) -> None:
    mistakes = LIST_ITEM.findall(_block_body(_section_body(guide, stage), "The mistakes"))
    assert len(mistakes) >= 3, f"{stage.value}: {len(mistakes)} mistakes, the minimum is three"
    for mistake in mistakes:
        assert "Symptom:" in mistake, f"{stage.value}: a mistake has no symptom: {mistake}"


@pytest.mark.parametrize("stage", list(JOB_STAGE_ORDER), ids=lambda stage: stage.value)
def test_what_good_looks_like_is_grounded_in_an_example(guide: str, stage: JobStage) -> None:
    body = _block_body(_section_body(guide, stage), "What good looks like")
    assert "Example:" in body, f"{stage.value}: 'What good looks like' names no concrete example"


def test_the_guide_links_out_rather_than_restating_the_reference(guide: str) -> None:
    assert "](cli.md)" in guide, "the guide must send readers to the CLI reference"
    assert "](living-studio.md)" in guide, "the guide must send readers to the surfaces"
    # docs/cli.md owns the flag tables. A second copy here is a second thing to drift.
    assert not re.search(r"^\|\s*Option\s*\|", guide, re.MULTILINE), (
        "the guide repeats the reference's flag-table shape; link to docs/cli.md instead"
    )


def test_every_relative_link_resolves_from_where_the_guide_lives(guide: str) -> None:
    """The guide is read in two places, and both resolve a link against ``docs/``.

    GitHub renders the file where it sits; ``website/tools/markdown_render.py`` joins the
    link to the guide's own directory before deciding whether it can point at a rendered
    page. So a target written from the repo root — ``docs/cli.md`` inside ``docs/`` — is
    broken twice over, and nothing but this test would ever notice.
    """
    for target in LINK.findall(guide):
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", target, re.IGNORECASE):
            continue
        path = target.partition("#")[0]
        assert (GUIDE.parent / path).is_file(), f"link target does not exist: {target}"


def test_everything_labelled_unsupported_offers_a_supported_path(guide: str) -> None:
    """A stage the product only half supports must say what to do instead.

    There is deliberately no minimum count: the guide says what is true, and the truth of
    its commands is checked by running them below, not by a number of confessions here.
    """
    for match in re.finditer(re.escape(UNSUPPORTED), guide):
        tail = guide[match.end() : match.end() + 500]
        assert re.search(r"\]\(|http|docs/", tail), (
            f"an unsupported step is labelled at {match.start()} without a supported path "
            "or a link to where it is tracked"
        )


def _lines(text: str) -> list[str]:
    commands: list[str] = []
    for block in BASH_BLOCK.finditer(text):
        for line in block.group("body").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            assert stripped.startswith(ENTRY_PREFIXES), (
                f"the guide shows a command this test cannot run: {stripped}"
            )
            commands.append(stripped)
    return commands


def _argv(line: str, ids: dict[str, str]) -> list[str]:
    prefix_length = max(
        (len(prefix.split()) for prefix in ENTRY_PREFIXES if line.startswith(prefix + " ")),
        default=0,
    )
    resolved: list[str] = []
    for token in shlex.split(line)[prefix_length:]:
        for name, value in ids.items():
            token = token.replace(f"${name}", value)
        unresolved = re.search(r"\$([A-Z_]+)", token)
        assert unresolved is None, f"${unresolved.group(1)} is used before the guide creates it"
        resolved.append(token)
    return resolved


def _record(line: str, output: str, ids: dict[str, str]) -> None:
    """Learn a placeholder from the id the guide's own command printed."""
    creator = next(
        (name for group, name in _CREATORS.items() if re.match(rf"^\S+ {group} ", f"{line} ")),
        None,
    )
    if creator is None:
        return
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return
    records = parsed if isinstance(parsed, list) else [parsed]
    for record in reversed(records):
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            ids[creator] = record["id"]
            return


def test_every_command_in_the_guide_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The guide exports a file with a relative name, so it lands here and not in the tree.
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "method-guide.db"
    runner = CliRunner()
    ids: dict[str, str] = {}
    for line in _lines(GUIDE.read_text(encoding="utf-8")):
        result = runner.invoke(
            app, ["--db", str(db_path), *_argv(line, ids)], catch_exceptions=False
        )
        assert result.exit_code == 0, f"{line}\nexit {result.exit_code}\n{result.output}"
        _record(line, result.output, ids)
    for name in ("JOB_ID", "STEP_ID", "OUTCOME_ID", "EVIDENCE_ID", "SEGMENT_ID"):
        assert name in ids, f"the guide never creates a {name}"


def test_the_cli_points_at_the_guide_from_inside_the_tool() -> None:
    result = CliRunner().invoke(app, ["guidelines"])
    assert result.exit_code == 0
    assert "docs/method.md" in result.output, (
        "`agentic-odi guidelines` must point at the practitioner guide"
    )


def test_the_readme_links_the_guide() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert re.search(r"^\|\s*\[[^\]]*\]\(docs/method\.md\)\s*\|", readme, re.MULTILINE), (
        "the README Documentation table has no row for docs/method.md"
    )
