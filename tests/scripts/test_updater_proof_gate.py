"""Where the updater's proof gets read (#613).

Three scheduled runs of `updater-e2e` died on the same assertion while the install
half stayed green, and the result went nowhere: the job sat outside every gate, so a
release could ship "it updates itself" on a proof that had never passed. The issue
calls leaving it dispatch-only unacceptable, so the decision is recorded in the files
themselves and locked here — a future edit that drops the gate is a red test, not a
quiet regression.

The constraint that shapes the choice: `ci-green` aggregates every job it needs, and a
`skipped` result fails it, so a schedule-only job cannot join that list. That is why
the proof moves to the release, where the decision is actually made.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
TAURI = WORKFLOWS / "tauri-release.yml"

PROOF_SCRIPT = "scripts/verify-desktop-update.sh"
WAIT_TEST = "scripts/tests/desktop_update_wait_e2e.sh"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _body(path: Path) -> str:
    """File text with comments dropped: what GitHub runs, not what we wrote about it."""
    return "\n".join(line for line in _text(path).splitlines() if not line.lstrip().startswith("#"))


def _flat(text: str) -> str:
    """Text with comments kept and whitespace collapsed, so a phrase can be matched
    across the line wrap a YAML comment has to use."""
    return re.sub(r"\s+", " ", text)


def _job(text: str, name: str) -> str:
    """One job's block, up to the next top-level job key."""
    start = text.index(f"\n  {name}:\n") + 1
    rest = text[start:]
    following = re.search(r"^  [a-z][a-z0-9-]*:$", rest[rest.index("\n") + 1 :], re.MULTILINE)
    return rest[: rest.index("\n") + 1 + following.start()] if following else rest


def test_the_desktop_release_runs_the_updater_proof() -> None:
    body = _body(TAURI)
    assert PROOF_SCRIPT in body, "the release must run the proof, not merely mention it"
    assert "xvfb-run" in body, "the proof launches the app and needs a display"


def test_the_release_build_waits_for_that_proof() -> None:
    """A job nobody needs is a job whose failure changes nothing."""
    build = _job(_body(TAURI), "build")
    assert "updater-proof" in build.split("needs:", 1)[1].split("\n", 1)[0], (
        "the build job must list updater-proof in its needs, or bundles ship unproven"
    )


def test_the_proof_checks_the_tree_being_released() -> None:
    """A weekly run on main proves last week's code; a release ships this tag."""
    proof = _job(_body(TAURI), "updater-proof")
    assert "ref: ${{ needs.resolve.outputs.tag }}" in proof


def test_the_gate_choice_and_its_reason_are_written_in_the_workflow() -> None:
    text = _text(TAURI)
    comment = text[: text.index("jobs:")]
    for phrase in ("#613", "ci-green", "skipped"):
        assert phrase in comment, f"the header must state the choice and why, naming {phrase!r}"
    assert "never blocks a pull request" in _flat(_job(text, "updater-proof"))


def test_an_override_is_recorded_rather_than_silent() -> None:
    """Emergency shipping stays possible, but the run summary has to say it happened."""
    body = _body(TAURI)
    assert "skip_updater_proof" in body
    proof = _job(body, "updater-proof")
    assert "GITHUB_STEP_SUMMARY" in proof, "an override must be written where people read it"
    assert "proven" in proof.lower() or "unproven" in proof.lower()


def test_the_weekly_ci_job_stays_out_of_the_pull_request_gate() -> None:
    """The reason the gate is not `ci-green`: a schedule-only job reports `skipped`
    on every pull request, and the aggregate treats that as a failure."""
    ci_green = _job(_body(CI), "ci-green")
    assert "updater-e2e" not in ci_green, "adding it to ci-green turns every PR red"


def test_the_wait_that_failed_is_covered_by_a_fast_ci_test() -> None:
    """The proof itself takes ~40 minutes to build two AppImages, so the half that
    broke needs a guard the pull request pipeline can actually run."""
    body = _body(CI)
    smoke = _job(body, "smoke")
    assert WAIT_TEST in smoke, "the polled wait must run in the smoke job, not only by hand"


def test_the_documentation_says_where_the_proof_gates() -> None:
    doc = _text(ROOT / "docs" / "installation.md")
    assert "updater-proof" in doc, "docs must name the job that reads the proof"
    assert WAIT_TEST in doc, "docs must name the fast test a contributor can run"
    assert PROOF_SCRIPT in doc
