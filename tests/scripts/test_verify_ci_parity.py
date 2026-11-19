"""The pre-PR gate must account for every job the merge waits on.

`scripts/verify.py` is the documented bar for opening a pull request, and
`CI green` is the status check the ``main-requires-ci-green`` ruleset requires.
Those were two separate lists kept by hand. The gate quietly fell behind: it
never ran ``ruff format --check``, the documentation checks, bandit, version
parity, the brand render, or the Studio's lint and typecheck, so a pull request
could run the documented pre-PR tier, see PASSED, and still open red on a
required job. Worse, a studio-only or website-only diff selected no command at
all and still printed PASSED.

These tests pin the contract in both directions: every job in
``ci-green.needs`` is either covered by a tier or declared CI-only with a
reason, and the planner actually selects the checks its coverage entry claims.
"""

from __future__ import annotations

from pathlib import Path

import verify
import yaml

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"


def _workflow() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def _required_jobs() -> set[str]:
    needs = _workflow()["jobs"]["ci-green"]["needs"]
    assert isinstance(needs, list), "`ci-green.needs` must stay a list of job ids"
    return set(needs)


def test_every_required_job_is_accounted_for() -> None:
    """A new required job must be covered or declared CI-only, not ignored."""
    accounted = set(verify.CI_JOB_COVERAGE) | set(verify.CI_ONLY_REASONS)
    required = _required_jobs()

    assert accounted == required, (
        "scripts/verify.py and .github/workflows/ci.yml disagree about the required jobs. "
        f"Required but unaccounted for: {sorted(required - accounted)}. "
        f"Accounted for but no longer required: {sorted(accounted - required)}."
    )


def test_every_accounted_job_exists_in_the_workflow() -> None:
    """A typo in the contract would otherwise hide a required job behind a fake name."""
    jobs = set(_workflow()["jobs"])
    unknown = sorted((set(verify.CI_JOB_COVERAGE) | set(verify.CI_ONLY_REASONS)) - jobs)

    assert not unknown, f"scripts/verify.py names jobs ci.yml does not define: {unknown}"


def test_a_covered_job_is_not_also_declared_ci_only() -> None:
    both = sorted(
        job
        for job, tiers in verify.CI_JOB_COVERAGE.items()
        if tiers and job in verify.CI_ONLY_REASONS
    )

    assert not both, f"these jobs are covered and also declared CI-only: {both}"


def test_every_ci_only_job_says_why() -> None:
    """The reason is the whole value of the declaration: it tells a reviewer what
    the local gate did not look at, and why that is acceptable."""
    unexplained = sorted(
        job
        for job, tiers in verify.CI_JOB_COVERAGE.items()
        if not tiers and not verify.CI_ONLY_REASONS.get(job, "").strip()
    )

    assert not unexplained, f"CI-only jobs with no reason: {unexplained}"
    assert set(verify.CI_ONLY_REASONS) == {
        job for job, tiers in verify.CI_JOB_COVERAGE.items() if not tiers
    }, "CI_ONLY_REASONS must describe exactly the jobs with no local tier"


def test_every_covered_job_names_real_tiers() -> None:
    unknown = sorted(
        f"{job}:{tier}"
        for job, tiers in verify.CI_JOB_COVERAGE.items()
        for tier in tiers
        if tier not in verify.TIERS
    )

    assert not unknown, f"coverage claims tiers that do not exist: {unknown}"


def _names(steps: list[verify.Step]) -> set[str]:
    return {step.name for step in steps}


def test_a_studio_only_diff_runs_the_studio_checks() -> None:
    """This diff used to select no command at all and print PASSED."""
    steps = verify.plan_changed(["apps/studio/src/App.tsx"])
    names = _names(steps)

    assert {"studio lint", "studio typecheck"} <= names
    assert not any("website" in name for name in names)
    assert not any(name.startswith("pytest (selected") for name in names)


def test_a_website_only_diff_runs_the_site_suite() -> None:
    """This diff used to select no command at all and print PASSED."""
    names = _names(verify.plan_changed(["website/tools/build_site.py"]))

    assert "website pytest" in names
    assert not any("studio" in name for name in names)


def test_a_python_diff_runs_the_format_check_it_used_to_skip() -> None:
    names = _names(verify.plan_changed(["packages/core/src/agentic_odi_core/models.py"]))

    assert "ruff check (touched paths)" in names
    assert "ruff format --check (touched paths)" in names
    assert "bandit (apps + packages)" in names


def test_a_docs_only_diff_runs_the_invariant_checks() -> None:
    """Version parity and generated blocks can drift from a docs edit."""
    names = _names(verify.plan_changed(["docs/architecture/testing.md"]))

    assert "version parity" in names
    assert "generated documentation blocks are current" in names
    assert "documentation matches the code" in names


def test_the_default_tier_contains_the_fast_tier() -> None:
    files = ["apps/studio/src/App.tsx"]
    fast = _names(verify.plan_changed(files))
    default = _names(verify.plan_default(files))

    assert fast <= default
    assert {"mypy (workspace)", "studio unit tests", "studio build"} <= default


def test_the_full_tier_runs_the_repo_wide_checks() -> None:
    names = _names(verify.plan_full())

    assert {
        "ruff check (repo)",
        "ruff format --check (repo)",
        "mypy (workspace)",
        "website build",
        "studio bundle budget",
    } <= names


def test_an_empty_diff_fails_instead_of_passing(monkeypatch) -> None:
    monkeypatch.setattr(verify, "get_changed_files", lambda base, head: [])
    calls: list[tuple] = []
    monkeypatch.setattr(verify, "run_cmd", lambda *args, **kwargs: calls.append(args) or (0, 0.0))

    assert verify.verify_changed("origin/main", "HEAD") == 1
    assert calls == [], "an empty diff must not run anything or report success"


def test_a_diff_that_selects_no_check_fails_instead_of_passing(monkeypatch) -> None:
    """The guard, tested directly: a planner returning nothing is an error."""
    monkeypatch.setattr(verify, "get_changed_files", lambda base, head: ["docs/testing.md"])
    monkeypatch.setattr(verify, "plan_changed", lambda files: [])
    calls: list[tuple] = []
    monkeypatch.setattr(verify, "run_cmd", lambda *args, **kwargs: calls.append(args) or (0, 0.0))

    assert verify.verify_changed("origin/main", "HEAD") == 1
    assert calls == []
