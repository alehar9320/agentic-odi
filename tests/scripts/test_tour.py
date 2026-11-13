"""The terminal tour is a generated artifact, so it can be held to a checksum.

A hand-written demo goes stale silently. Here every command in
``docs/tour/script.md`` is executed against a throwaway workspace by
``scripts/tour.py``, and the committed cast, README and manifest are just the
output of that run. These tests regenerate into a temp directory and compare: a
command that no longer runs, or a capture someone hand-edited, fails here rather
than in front of a stranger trying to follow the tour.

Nothing here touches the network, a model, or a real user's store.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import tour

ROOT = Path(__file__).resolve().parents[2]
TOUR_DIR = ROOT / "docs" / "tour"
ASSETS = ("tour.cast", "README.md", "manifest.json")

BROKEN_SCRIPT = """# A tour that cannot be recorded

## 1. Run something the CLI does not have

```bash
uv run agentic-odi this-command-does-not-exist
```
"""


@pytest.fixture
def broken_script(tmp_path: Path) -> Path:
    path = tmp_path / "script.md"
    path.write_text(BROKEN_SCRIPT, encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def captured(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """One real walkthrough, into a throwaway workspace."""
    return tour.generate(workspace=tmp_path_factory.mktemp("tour"))


# --- the script itself -------------------------------------------------------


def test_the_script_holds_the_ordered_commands() -> None:
    commands = tour.load_script()
    assert commands, "docs/tour/script.md has no fenced commands"
    # The tour is the loop, so it must start from the fixture and reach a strategy.
    assert any("gen_corpus.py" in command for command in commands), (
        "the tour never loads the demo fixture"
    )
    assert any("strategy" in command for command in commands), "the tour never reaches the strategy"


def test_the_script_is_an_ordered_list_of_one_command_steps() -> None:
    """The script is a walkthrough, so each numbered step is exactly one command."""
    titles = tour.step_titles()
    assert [int(title.split(".")[0]) for title in titles] == list(range(1, len(titles) + 1)), (
        "the step numbers must run 1..N with no gaps"
    )
    assert len(titles) == len(tour.load_script())


def test_the_script_stays_offline_and_model_free() -> None:
    for command in tour.load_script():
        forbidden = (" http", " https", "curl", " chat", "--backend mcp", "npm ", "playwright")
        assert not any(token in command for token in forbidden), (
            f"this command needs a model or the network: {command}"
        )


# --- execution ---------------------------------------------------------------


def test_the_manifest_accounts_for_every_command(captured: dict[str, str]) -> None:
    manifest = json.loads(captured["manifest.json"])
    assert manifest["steps"] == len(tour.load_script()), (
        "the manifest does not account for every command in the script"
    )


def test_a_command_that_cannot_run_fails_and_names_the_step(
    tmp_path: Path, broken_script: Path
) -> None:
    with pytest.raises(tour.TourError) as failure:
        tour.capture(workspace=tmp_path / "run", script=broken_script)
    assert "this-command-does-not-exist" in str(failure.value)
    assert "step 1" in str(failure.value), "the failure must say which step broke"


def test_a_failed_capture_leaves_good_assets_in_place(
    tmp_path: Path, broken_script: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Half a tour is worse than the last complete one, so failure must not write."""
    destination = tmp_path / "out"
    destination.mkdir()
    for name, text in tour.generate(workspace=tmp_path / "seed").items():
        (destination / name).write_text(text, encoding="utf-8")
    before = {name: (destination / name).read_text(encoding="utf-8") for name in ASSETS}

    # The documented regeneration command reports failure and exits non-zero; a person
    # running it gets a message, not a traceback.
    assert tour.main(["--out", str(destination), "--script", str(broken_script)]) == 1

    after = {name: (destination / name).read_text(encoding="utf-8") for name in ASSETS}
    assert after == before, "a failed capture overwrote good assets"
    assert "tour failed" in capsys.readouterr().err


# --- determinism -------------------------------------------------------------


def test_two_runs_produce_the_same_bytes(tmp_path: Path) -> None:
    first = tour.generate(workspace=tmp_path / "a")
    second = tour.generate(workspace=tmp_path / "b")
    for name in ASSETS:
        assert first[name] == second[name], f"{name} is not reproducible"


def test_the_committed_assets_match_a_fresh_run(tmp_path: Path) -> None:
    """The drift check: a stale or hand-edited capture fails here."""
    fresh = tour.generate(workspace=tmp_path)
    for name in ASSETS:
        committed = (TOUR_DIR / name).read_text(encoding="utf-8")
        assert committed == fresh[name], (
            f"docs/tour/{name} is stale — regenerate with `uv run python scripts/tour.py --write`"
        )


# --- isolation ---------------------------------------------------------------


def test_the_tour_never_touches_the_environment_store(tmp_path: Path, monkeypatch) -> None:
    store = tmp_path / "someone-elses-workspace.db"
    store.write_bytes(b"must-not-change")
    monkeypatch.setenv("AGENTIC_ODI_DB", str(store))

    tour.generate(workspace=tmp_path / "tour")

    assert store.read_bytes() == b"must-not-change", "the tour wrote to the ambient store"


def test_generating_writes_nothing_into_the_repository(tmp_path: Path) -> None:
    """The tour's artifacts stay inside its workspace, including the export.

    A placeholder that is only half substituted — `$TOUR_OUT/study.json`, where the
    variable is part of a longer token — would create a literal `$TOUR_OUT` directory
    in the working tree. That is what this catches.
    """
    before = {path.name for path in ROOT.iterdir()}
    watched = {path.name: path.read_bytes() for path in TOUR_DIR.iterdir() if path.is_file()}

    tour.generate(workspace=tmp_path / "tour")

    assert {path.name for path in ROOT.iterdir()} == before, "the tour wrote into the working tree"
    assert {
        path.name: path.read_bytes() for path in TOUR_DIR.iterdir() if path.is_file()
    } == watched
    assert (tmp_path / "tour" / "out" / "study.json").is_file(), (
        "the export did not land in the tour's own workspace"
    )


# --- what the artifacts claim ------------------------------------------------


def test_the_cast_is_asciicast_v2(captured: dict[str, str]) -> None:
    lines = [line for line in captured["tour.cast"].splitlines() if line.strip()]
    header = json.loads(lines[0])
    assert header["version"] == 2
    assert header["width"] and header["height"]
    assert header["title"], "the cast carries no title"
    for line in lines[1:]:
        event = json.loads(line)
        assert event[1] == "o", f"unexpected event stream: {event}"
        assert isinstance(event[0], float)


def test_the_assets_label_the_data_as_sample(captured: dict[str, str]) -> None:
    for name in ("README.md", "tour.cast"):
        assert tour.SAMPLE_LABEL in captured[name], f"{name} does not say the data is sample data"


def test_the_readme_states_the_budget_and_the_measured_playback(captured: dict[str, str]) -> None:
    readme = captured["README.md"]
    assert f"{tour.PLAYBACK_BUDGET_SECONDS} seconds" in readme
    # The playback figure comes from the pinned pacing, never from a promise.
    steps = len(tour.load_script())
    assert f"{tour.playback_seconds(steps):.2f} s" in readme


def test_the_tour_ends_where_the_terminal_actually_stops(captured: dict[str, str]) -> None:
    """No capability the product lacks may appear in the tour.

    The decision brief is rendered in the browser (`apps/studio/src/lib/brief.ts`), not in
    a terminal, so the cast has to stop at what the terminal really produces and name the
    browser half instead of implying a terminal brief exists.
    """
    assert "not in the terminal" in captured["README.md"].lower()


# --- reachability ------------------------------------------------------------


def test_regeneration_is_one_documented_command() -> None:
    development = (ROOT / "docs" / "development.md").read_text(encoding="utf-8")
    assert "uv run python scripts/tour.py --write" in development, (
        "docs/development.md must carry the one command that regenerates the tour"
    )


def test_the_readme_links_the_tour() -> None:
    assert "docs/tour/README.md" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_walkthrough_fits_the_ninety_second_budget(tmp_path: Path) -> None:
    """Measured, not promised: the real commands, timed, against the parent's budget."""
    started = time.perf_counter()
    tour.generate(workspace=tmp_path)
    elapsed = time.perf_counter() - started
    assert elapsed < tour.PLAYBACK_BUDGET_SECONDS, (
        f"the walkthrough took {elapsed:.1f}s against a {tour.PLAYBACK_BUDGET_SECONDS}s budget"
    )
