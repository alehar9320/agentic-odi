"""Focused verification gate (issue #754).

Runs the subset of CI a local machine can run, selected by touched paths, in
three tiers with a printed time budget. The fast tiers fit the 10-30 minute
agent ceiling; CI still owns the matrix that needs browsers, Rust, the network,
or more than one Python version.

Every job that gates the `CI green` aggregate is either covered by a tier here
or declared in `CI_ONLY_REASONS` with the reason it cannot be. That mapping is
a contract, not a comment: `tests/scripts/test_verify_ci_parity.py` fails when
this file and `.github/workflows/ci.yml` disagree about which jobs exist.

A diff that selects no check is a failure. The gate used to print PASSED after
running nothing for a studio-only or website-only diff, which made it report on
work it had never looked at.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass

WORKSPACE_MEMBERS = (
    "apps/cli",
    "apps/mcp-server",
    "apps/studio-api",
    "packages/connectors",
    "packages/core",
)

# Map top-level directories/files to test targets
PYTHON_PACKAGES = set(WORKSPACE_MEMBERS)

STUDIO_DIR = "apps/studio"
WEBSITE_DIR = "website"

BUDGET_CEILING_SECONDS = 300  # per command ceiling
TOTAL_BUDGET_MINUTES = 30  # total including cold uv sync

TIERS = ("changed", "default", "full")

# --- The contract with .github/workflows/ci.yml ---------------------------
#
# One entry per job in `ci-green.needs`. A job maps to the tiers that run its
# substantive check locally, or is listed in CI_ONLY_REASONS instead. Adding a
# required job to CI without deciding which side it belongs on fails
# `tests/scripts/test_verify_ci_parity.py`.
CI_JOB_COVERAGE: dict[str, tuple[str, ...]] = {
    "lint": ("changed", "default", "full"),
    "typecheck": ("default", "full"),
    "security": ("changed", "default", "full"),
    "dependencies": (),
    "test": ("changed", "default", "full"),
    "smoke": (),
    "website": ("changed", "default", "full"),
    "studio": ("changed", "default", "full"),
    "contrast": (),
    "tauri-check": (),
    "tauri-build": (),
    "e2e": (),
    "e2e-smoke": (),
}

CI_ONLY_REASONS: dict[str, str] = {
    "dependencies": (
        "audits three lockfiles against advisory databases; needs the network and does not "
        "depend on the diff (run it when a dependency changes; see docs/development.md)"
    ),
    "smoke": (
        "starts both services and probes them over HTTP on fixed ports; a real boot, "
        "not a unit test"
    ),
    "contrast": "drives Chromium against a built Studio; browser lane",
    "tauri-check": "needs the Rust toolchain and the Linux webview libraries",
    "tauri-build": (
        "builds and bundles the desktop app; needs the Rust toolchain and the webview libraries"
    ),
    "e2e": (
        "drives Chromium against a built Studio and both services; advisory at merge time "
        "and owned by the e2e lane"
    ),
    "e2e-smoke": (
        "drives Chromium against the built Studio and both services; advisory at merge "
        "time and owned by the e2e lane"
    ),
}

TIER_NOTES = {
    "changed": (
        "Not run: mypy, studio unit tests/build, website build, e2e, tauri, dependency audit."
    ),
    "default": "Not run: e2e (owned by the e2e lane), tauri, dependency audit.",
    "full": ("Not run: e2e (owned by the e2e lane), tauri-check, tauri-build, dependency audit."),
}


class VerifyError(Exception):
    pass


@dataclass(frozen=True)
class Step:
    """One command the gate runs, named so the plan can be asserted in a test."""

    name: str
    argv: tuple[str, ...]

    @property
    def command(self) -> str:
        return " ".join(self.argv)


def run_cmd(cmd: list[str], env: dict[str, str] | None = None) -> tuple[int, float]:
    start = time.time()
    print(f"  $ {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, env=env)
        elapsed = time.time() - start
        print(f"    elapsed: {elapsed:.1f}s")
        return result.returncode, elapsed
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        elapsed = time.time() - start
        print(f"    elapsed: {elapsed:.1f}s (error: {e})")
        return 127, elapsed


def get_changed_files(base: str = "origin/main", head: str = "HEAD") -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...{head}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            # try without merge-base
            result = subprocess.run(
                ["git", "diff", "--name-only", base, head],
                capture_output=True,
                text=True,
                check=False,
            )
        if result.returncode != 0:
            # try just HEAD vs working tree
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        return files
    except (subprocess.SubprocessError, OSError):
        return []


def map_files_to_targets(files: list[str]) -> dict[str, set[str] | bool]:
    targets: dict[str, set[str] | bool] = {
        "python_packages": set(),
        "studio": False,
        "website": False,
        "scripts": False,
        "tests_root": False,
        "brand": False,
        "unmapped": set(),
    }
    for f in files:
        path = f.replace("\\", "/")
        if path.startswith("./"):
            path = path[2:]
        mapped = False
        # Check python packages
        for member in WORKSPACE_MEMBERS:
            if path.startswith(f"{member}/") or path == member:
                targets["python_packages"].add(member)  # type: ignore[union-attr]
                mapped = True
                break
        if mapped:
            continue
        if path.startswith("apps/studio/"):
            targets["studio"] = True
            mapped = True
            continue
        if path.startswith("website/"):
            targets["website"] = True
            mapped = True
            continue
        if path.startswith("scripts/"):
            targets["scripts"] = True
            mapped = True
            continue
        if path.startswith("security/"):
            # The accepted-advisory ledger is read by tests/scripts/test_audit_ignore.py,
            # so an edit to it is covered by the same target as the script that parses it.
            targets["scripts"] = True
            mapped = True
            continue
        if path.startswith("tests/"):
            targets["tests_root"] = True
            mapped = True
            continue
        if path.startswith("infra/"):
            # The Cloudflare Worker is TypeScript with no JS runner here, so its
            # contract is pinned by the root suite (`tests/test_worker_*.py`).
            targets["tests_root"] = True
            mapped = True
            continue
        if path.startswith("brand/"):
            targets["brand"] = True
            mapped = True
            continue
        if path.startswith(".qoder/"):
            # Agent worktree state must never reach the index: a gitlink there
            # breaks actions/checkout's submodule cleanup. The contract test
            # that pins the invariant is the target for adding or dropping one.
            targets["tests_root"] = True
            mapped = True
            continue

        # Markdown and agent-facing docs are covered by the documentation drift
        # test and the root suite. A docs-only PR must still be verifiable, and
        # handing .md paths to ruff would fail for the wrong reason.
        if path.startswith(("docs/", ".agents/")) or path.endswith(".md"):
            targets["tests_root"] = True
            mapped = True
            continue
        if path == "pyproject.toml" or path == "uv.lock" or path.startswith(".github/"):
            # affects everything - map to all packages for --changed to be safe
            for member in WORKSPACE_MEMBERS:
                targets["python_packages"].add(member)  # type: ignore[union-attr]
            targets["studio"] = True
            mapped = True
            continue
        if not mapped:
            targets["unmapped"].add(path)  # type: ignore[union-attr]
    return targets


def _python_files(files: list[str]) -> list[str]:
    return [f for f in files if f.endswith((".py", ".pyi"))]


def _paths_under(files: list[str], prefix: str) -> bool:
    return any(f.replace("\\", "/").startswith(prefix) for f in files)


def plan_changed(files: list[str]) -> list[Step]:
    """The fast tier: every required check that is a function of the diff.

    The invariant checks are deliberately path-independent. Version parity and
    the generated documentation blocks can drift from any edit, are cheap, and
    are the two checks CI most often caught after `--changed` had passed.
    """
    targets = map_files_to_targets(files)
    python_files = _python_files(files)
    steps: list[Step] = []

    # `lint`: ruff over the touched files (a docs-only diff has no Python to lint).
    if python_files:
        steps.append(
            Step("ruff check (touched paths)", ("uv", "run", "ruff", "check", *python_files))
        )
        steps.append(
            Step(
                "ruff format --check (touched paths)",
                ("uv", "run", "ruff", "format", "--check", *python_files),
            )
        )

    # `lint` and `docs`: invariants that do not depend on which files changed.
    steps.append(
        Step(
            "version parity",
            ("uv", "run", "python", "scripts/check_version_parity.py"),
        )
    )
    steps.append(
        Step(
            "generated documentation blocks are current",
            ("uv", "run", "python", "scripts/docs_index.py", "--check"),
        )
    )
    steps.append(
        Step(
            "documentation matches the code",
            ("uv", "run", "python", "scripts/doc_check.py"),
        )
    )

    # `security`: bandit only understands Python, so it is selected by path.
    if _paths_under(python_files, "apps/") or _paths_under(python_files, "packages/"):
        steps.append(
            Step(
                "bandit (apps + packages)",
                ("uv", "run", "bandit", "-c", "pyproject.toml", "-r", "apps", "packages"),
            )
        )
    if _paths_under(python_files, "website/"):
        steps.append(
            Step(
                "bandit (website)",
                ("uv", "run", "bandit", "-c", "pyproject.toml", "-r", "website/"),
            )
        )

    # `lint`: the mascot assets are generated; a source edit without regeneration
    # is a red lint job and invisible to a diff that only ran ruff.
    if targets["brand"]:
        steps.append(
            Step(
                "brand assets match the generator",
                ("uv", "run", "python", "brand/tools/render.py", "--check"),
            )
        )

    # `test`: pytest for the selected packages.
    pkg_args = sorted(targets["python_packages"])  # type: ignore[arg-type]
    if targets["tests_root"]:
        pkg_args.append("tests")
    if targets["scripts"]:
        pkg_args.append("tests/scripts")
    if targets["brand"]:
        pkg_args.append("brand")
    if pkg_args:
        steps.append(Step("pytest (selected packages)", ("uv", "run", "pytest", "-q", *pkg_args)))

    # `studio`: lint and typecheck are the two halves of the studio job that do
    # not need a build; the old gate ran neither for a studio-only diff.
    if targets["studio"]:
        steps.append(Step("studio lint", ("npm", "--prefix", STUDIO_DIR, "run", "lint")))
        steps.append(Step("studio typecheck", ("npm", "--prefix", STUDIO_DIR, "run", "typecheck")))

    # `website`: the site suite is a real gate in CI, so it is a real gate here.
    if targets["website"]:
        steps.append(
            Step(
                "website pytest",
                ("uv", "run", "--directory", WEBSITE_DIR, "pytest", "tests/"),
            )
        )

    return steps


def plan_default(files: list[str]) -> list[Step]:
    """The merge-review tier: the fast tier plus type checking and the builds."""
    targets = map_files_to_targets(files)
    steps = plan_changed(files)

    # `typecheck`: CI runs the whole workspace, not only the touched packages, so
    # a cross-package type change cannot hide behind a narrow mypy invocation.
    steps.append(Step("mypy (workspace)", ("uv", "run", "mypy", "apps", "brand", "packages")))
    if targets["website"]:
        steps.append(
            Step(
                "mypy (website)",
                ("uv", "run", "--directory", WEBSITE_DIR, "mypy", "."),
            )
        )

    if targets["studio"]:
        steps.append(
            Step("studio unit tests", ("npm", "--prefix", STUDIO_DIR, "test", "--", "--run"))
        )
        steps.append(Step("studio build", ("npm", "--prefix", STUDIO_DIR, "run", "build")))
        steps.append(
            Step(
                "studio bundle budget",
                ("node", "scripts/check_bundle_budget.mjs"),
            )
        )

    if targets["website"]:
        steps.append(
            Step(
                "website build",
                ("uv", "run", "python", "website/tools/build_site.py", "--out", "_site"),
            )
        )

    return steps


def plan_full() -> list[Step]:
    """The full matrix, minus the lanes that need a browser, Rust, or the network."""
    return [
        Step("ruff check (repo)", ("uv", "run", "ruff", "check", ".")),
        Step("ruff format --check (repo)", ("uv", "run", "ruff", "format", "--check", ".")),
        Step(
            "version parity",
            ("uv", "run", "python", "scripts/check_version_parity.py"),
        ),
        Step(
            "brand assets match the generator",
            ("uv", "run", "python", "brand/tools/render.py", "--check"),
        ),
        Step(
            "documentation matches the code",
            ("uv", "run", "python", "scripts/doc_check.py"),
        ),
        Step(
            "generated documentation blocks are current",
            ("uv", "run", "python", "scripts/docs_index.py", "--check"),
        ),
        Step(
            "bandit (apps + packages)",
            ("uv", "run", "bandit", "-c", "pyproject.toml", "-r", "apps", "packages"),
        ),
        Step(
            "bandit (website)",
            ("uv", "run", "bandit", "-c", "pyproject.toml", "-r", "website/"),
        ),
        Step("mypy (workspace)", ("uv", "run", "mypy", "apps", "brand", "packages")),
        Step("mypy (website)", ("uv", "run", "--directory", WEBSITE_DIR, "mypy", ".")),
        Step("pytest (all)", ("uv", "run", "pytest")),
        Step("website pytest", ("uv", "run", "--directory", WEBSITE_DIR, "pytest", "tests/")),
        Step(
            "website build",
            ("uv", "run", "python", "website/tools/build_site.py", "--out", "_site"),
        ),
        Step("studio lint", ("npm", "--prefix", STUDIO_DIR, "run", "lint")),
        Step("studio typecheck", ("npm", "--prefix", STUDIO_DIR, "run", "typecheck")),
        Step("studio unit tests", ("npm", "--prefix", STUDIO_DIR, "test", "--", "--run")),
        Step("studio build", ("npm", "--prefix", STUDIO_DIR, "run", "build")),
        Step("studio bundle budget", ("node", "scripts/check_bundle_budget.mjs")),
    ]


def print_coverage() -> None:
    """Print which tier covers each required CI job, and why the rest cannot be."""
    print("CI job coverage (every job `CI green` requires):")
    width = max(len(job) for job in CI_JOB_COVERAGE)
    for job in sorted(CI_JOB_COVERAGE):
        tiers = CI_JOB_COVERAGE[job]
        if tiers:
            print(f"  {job:<{width}}  {', '.join('--' + tier for tier in tiers)}")
            continue
        print(f"  {job:<{width}}  CI only - {CI_ONLY_REASONS[job]}")
    print(
        "  Coverage is a contract: tests/scripts/test_verify_ci_parity.py fails when "
        "this table and ci.yml disagree."
    )
    print()


def _run_steps(tier: str, steps: list[Step], files: list[str] | None) -> int:
    if files is not None and not files:
        print("ERROR: the diff against the base ref is empty; nothing was verified.")
        print("Selection must never turn an empty diff into a passing report.")
        return 1
    if not steps:
        print("ERROR: this run selected no checks, so there is nothing to report on.")
        print("Selection must never make a failing check invisible.")
        return 1

    failed = False
    total = len(steps)
    for index, step in enumerate(steps, start=1):
        print(f"[{index}/{total}] {step.name}")
        code, _ = run_cmd(list(step.argv))
        if code != 0:
            failed = True
        print()

    print(f"Checks run: {total}")
    print(TIER_NOTES[tier])
    print()
    print_coverage()
    if failed:
        print(f"FAILED ({tier})")
        return 1
    print(f"PASSED ({tier})")
    return 0


def verify_changed(base: str = "origin/main", head: str = "HEAD") -> int:
    print("Tier: --changed (fast gate)")
    print(
        f"Budget: per-command ceiling {BUDGET_CEILING_SECONDS}s; total budget "
        f"{TOTAL_BUDGET_MINUTES} min including cold uv sync"
    )
    print()
    files = get_changed_files(base, head)
    print(f"Changed files: {len(files)}")
    for f in files:
        print(f"  - {f}")
    print()
    targets = map_files_to_targets(files)
    if targets["unmapped"]:
        print("ERROR: Unmapped touched files (must be mapped to a test target):")
        for f in sorted(targets["unmapped"]):  # type: ignore[arg-type]
            print(f"  - {f}")
        print(
            "\nSelection must never make a failing test invisible. Map these paths or add mapping."
        )
        return 1
    return _run_steps("changed", plan_changed(files), files)


def verify_default(base: str = "origin/main", head: str = "HEAD") -> int:
    print("Tier: --default")
    print(
        f"Budget: adds type checking, studio units/build, and the site build; "
        f"per-command ceiling {BUDGET_CEILING_SECONDS}s"
    )
    print()
    files = get_changed_files(base, head)
    print(f"Changed files: {len(files)}")
    for f in files:
        print(f"  - {f}")
    print()
    targets = map_files_to_targets(files)
    if targets["unmapped"]:
        print("ERROR: Unmapped touched files:")
        for f in sorted(targets["unmapped"]):  # type: ignore[arg-type]
            print(f"  - {f}")
        return 1
    return _run_steps("default", plan_default(files), files)


def verify_full() -> int:
    print("Tier: --full (everything CI runs on one Linux machine)")
    print("Budget: the local matrix; per-job budgets in CI are 5-20 min")
    print()
    return _run_steps("full", plan_full(), None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Focused verification gate")
    parser.add_argument("--changed", action="store_true", help="Fast gate on changed files")
    parser.add_argument(
        "--default",
        action="store_true",
        help="Adds type checks, studio units/build, and site build",
    )
    parser.add_argument("--full", action="store_true", help="Full local matrix (CI's job)")
    parser.add_argument("--base", default="origin/main", help="Base ref for diff")
    parser.add_argument("--head", default="HEAD", help="Head ref for diff")
    args = parser.parse_args(argv)

    if args.changed and not args.default and not args.full:
        return verify_changed(args.base, args.head)
    elif args.default and not args.changed and not args.full:
        return verify_default(args.base, args.head)
    elif args.full and not args.changed and not args.default:
        return verify_full()
    elif args.changed:
        return verify_changed(args.base, args.head)
    elif args.default:
        return verify_default(args.base, args.head)
    elif args.full:
        return verify_full()
    else:
        # default behavior
        parser.print_help()
        print("\nTip: --changed fits 10-30 minute agent budget; --full is CI's responsibility.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
