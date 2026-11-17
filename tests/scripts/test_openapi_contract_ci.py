"""The Studio OpenAPI drift check runs in CI and can fail the merge.

The contract check (``agentic_odi_studio_api.openapi --check``) is only worth
having if a stale ``apps/studio/openapi.json`` actually turns the build red.
This pins that wiring the way ``website/tests/test_ci_required.py`` pins the
site's: a job that runs the check, is not hidden behind ``continue-on-error``,
and is enforced by the ``CI green`` aggregate the merge ruleset requires.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"

_JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
CHECK_COMMAND = "agentic_odi_studio_api.openapi --check"


def _text() -> str:
    assert CI.is_file(), "missing .github/workflows/ci.yml"
    return CI.read_text(encoding="utf-8")


def _job(text: str, name: str) -> str:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line == f"  {name}:"), None)
    assert start is not None, f"no `{name}` job"
    for end in range(start + 1, len(lines)):
        header = _JOB_HEADER.match(lines[end])
        if header and header.group(1) != name:
            return "\n".join(lines[start:end])
    return "\n".join(lines[start:])


def test_a_ci_job_runs_the_contract_check() -> None:
    text = _text()
    jobs = {
        _JOB_HEADER.match(line).group(1) for line in text.splitlines() if _JOB_HEADER.match(line)
    }
    runners = [name for name in jobs if CHECK_COMMAND in _job(text, name)]
    assert runners, f"no CI job runs `{CHECK_COMMAND}`"


def test_the_contract_check_job_can_fail_the_build() -> None:
    text = _text()
    jobs = {
        _JOB_HEADER.match(line).group(1) for line in text.splitlines() if _JOB_HEADER.match(line)
    }
    for name in (n for n in jobs if CHECK_COMMAND in _job(text, n)):
        assert "continue-on-error" not in _job(text, name), (
            f"the `{name}` job runs the contract check but hides its failure"
        )


def test_ci_green_enforces_the_contract_check_job() -> None:
    text = _text()
    jobs = {
        _JOB_HEADER.match(line).group(1) for line in text.splitlines() if _JOB_HEADER.match(line)
    }
    runner = next(name for name in jobs if CHECK_COMMAND in _job(text, name))
    ci_green = _job(text, "ci-green")
    needs = ci_green.split("needs:", 1)[1].splitlines()[0]
    assert runner in needs, f"`CI green` must depend on the `{runner}` job"
    # `needs:` alone is not enough; the aggregate has to read the result.
    assert f"needs.{runner}.result" in ci_green, (
        f"`CI green` must read the `{runner}` result, not just depend on it"
    )
