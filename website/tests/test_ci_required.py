"""The website's tests run in CI, and the merge cannot ignore them.

The site is a product surface with real tests under ``website/tests/``, but a
workflow that runs them is easy to lose by accident, and this repository has
lost it twice:

* the site's checks once lived in a ``feature/gh-pages``-only ``website.yml``
  that never ran for a pull request into ``main`` (fixed by 402f0a5), and
* the Pages pre-deploy gate was written against ``website/index.html`` after
  that file had been deleted, so every deploy failed for two days.

These assertions pin the wiring, not the tests themselves: a CI job that runs
the site suite, carries no ``continue-on-error``, is a required input to the
``CI green`` aggregate (the status check the ``main-requires-ci-green`` ruleset
requires), and gates the Pages deploy.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
PAGES = ROOT / ".github" / "workflows" / "pages.yml"

# A top-level job key sits at exactly two spaces of indentation.
_JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")


def _text(path: Path) -> str:
    assert path.is_file(), f"missing {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def _job(text: str, name: str) -> str:
    """The block of a top-level job, from its key to the next job key."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line == f"  {name}:"), None)
    assert start is not None, f"no `{name}` job"
    for end in range(start + 1, len(lines)):
        header = _JOB_HEADER.match(lines[end])
        if header and header.group(1) != name:
            return "\n".join(lines[start:end])
    return "\n".join(lines[start:])


def _website_commands(job: str) -> str:
    """The job's ``run:`` steps joined into one searchable string."""
    return "\n".join(line.strip() for line in job.splitlines() if line.strip().startswith("run:"))


def test_the_website_job_runs_the_site_suite() -> None:
    job = _job(_text(CI), "website")
    commands = _website_commands(job)
    # The documented command, in either of its two spellings.
    runs_the_site_suite = ("pytest tests/" in commands and "--directory website" in commands) or (
        "pytest website/tests" in commands
    )
    assert runs_the_site_suite, (
        "the `website` CI job must run the site suite (`uv run --directory website pytest tests/`)"
    )


def test_the_website_job_never_hides_a_failure() -> None:
    job = _job(_text(CI), "website")
    assert "continue-on-error" not in job, "the website job must be able to fail CI"


def test_ci_green_needs_the_website_job() -> None:
    needs = _job(_text(CI), "ci-green").split("needs:", 1)[1].splitlines()[0]
    assert "website" in needs, "`CI green` must depend on the website job"


def test_ci_green_fails_when_the_website_job_fails() -> None:
    # `needs:` alone is not enough: the aggregate has to inspect the result.
    ci_green = _job(_text(CI), "ci-green")
    assert "needs.website.result" in ci_green, "`CI green` must read the website result"
    loop = next(
        (line for line in ci_green.splitlines() if "for job in" in line),
        "",
    )
    assert "WEBSITE" in loop, "the website result must be in the enforced job loop"


def test_ci_green_is_the_required_status_check() -> None:
    # The `main-requires-ci-green` ruleset requires a status check literally
    # named `CI green`; renaming the job would silently unrequire every job
    # it aggregates, including the website tests.
    assert "name: CI green" in _job(_text(CI), "ci-green")


def test_ci_runs_the_website_job_on_pull_requests() -> None:
    text = _text(CI)
    assert "pull_request:" in text, "CI must run on pull requests"
    assert "branches: [main]" in text


def test_pages_deploy_waits_for_the_tested_build() -> None:
    pages = _text(PAGES)
    build = _job(pages, "build")
    assert "pytest" in build, "the Pages build must run the site tests first"
    assert "continue-on-error" not in build, "the Pages build must be able to fail"
    deploy = _job(pages, "deploy")
    assert "needs: build" in deploy, "the Pages deploy must wait for the build job"
