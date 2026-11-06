"""Focused verification gate (issue #754).

Runs a subset of tests by touched paths, with three tiers and a printed time
budget. The fast tiers are designed for agents with a 10-30 minute ceiling;
CI still owns the full matrix.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

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


class VerifyError(Exception):
    pass


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


def map_files_to_targets(files: list[str]) -> dict[str, set[str]]:
    targets = {
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
                targets["python_packages"].add(member)
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
        if path.startswith("tests/"):
            targets["tests_root"] = True
            mapped = True
            continue
        if path.startswith("brand/"):
            targets["brand"] = True
            mapped = True
            continue
        if path == "pyproject.toml" or path == "uv.lock" or path.startswith(".github/"):
            # affects everything - map to all packages for --changed to be safe
            for member in WORKSPACE_MEMBERS:
                targets["python_packages"].add(member)
            targets["studio"] = True
            mapped = True
            continue
        if not mapped:
            targets["unmapped"].add(path)
    return targets


def verify_changed(base: str = "origin/main", head: str = "HEAD") -> int:
    print("Tier: --changed (fast gate)")
    print(
        f"Budget: designed for < 5 minutes on warm env; per-command ceiling {BUDGET_CEILING_SECONDS}s; total budget {TOTAL_BUDGET_MINUTES} min including cold uv sync"
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
        for f in sorted(targets["unmapped"]):
            print(f"  - {f}")
        print(
            "\nSelection must never make a failing test invisible. Map these paths or add mapping."
        )
        return 1

    failed = False
    # Ruff on touched paths
    if files:
        print("[1/2] ruff (touched paths)")
        code, _ = run_cmd(["uv", "run", "ruff", "check"] + files)
        if code != 0:
            failed = True
        print()

    # Pytest for selected packages
    if (
        targets["python_packages"]
        or targets["tests_root"]
        or targets["scripts"]
        or targets["brand"]
    ):
        print("[2/2] pytest (selected packages)")
        pkg_args = []
        for pkg in sorted(targets["python_packages"]):
            pkg_args.append(pkg)
        if targets["tests_root"]:
            pkg_args.append("tests")
        if targets["scripts"]:
            pkg_args.append("tests/scripts")
        if targets["brand"]:
            pkg_args.append("brand")
        if not pkg_args:
            pkg_args = ["tests/scripts"]  # minimal
        code, _ = run_cmd(["uv", "run", "pytest", "-q"] + pkg_args)
        if code != 0:
            failed = True
        print()
    elif targets["studio"]:
        print("[2/2] pytest (no Python packages touched)")
        print("  (skipping Python tests)")
        print()

    print(
        "Skipped tiers: --default adds mypy (touched packages) + vitest (touched studio); --full runs website, studio build, e2e"
    )
    print("not run: coverage, e2e, website, desktop")
    print()
    if failed:
        print("FAILED")
        return 1
    print("PASSED (--changed)")
    return 0


def verify_default(base: str = "origin/main", head: str = "HEAD") -> int:
    print("Tier: --default")
    print(
        f"Budget: adds type checking and studio units; per-command ceiling {BUDGET_CEILING_SECONDS}s"
    )
    print()
    files = get_changed_files(base, head)
    print(f"Changed files: {len(files)}")
    print()
    targets = map_files_to_targets(files)
    if targets["unmapped"]:
        print("ERROR: Unmapped touched files:")
        for f in sorted(targets["unmapped"]):
            print(f"  - {f}")
        return 1

    failed = False
    if files:
        print("[1/4] ruff (touched paths)")
        code, _ = run_cmd(["uv", "run", "ruff", "check"] + files)
        if code != 0:
            failed = True
        print()

    if (
        targets["python_packages"]
        or targets["tests_root"]
        or targets["scripts"]
        or targets["brand"]
    ):
        print("[2/4] pytest (selected packages)")
        pkg_args = []
        for pkg in sorted(targets["python_packages"]):
            pkg_args.append(pkg)
        if targets["tests_root"]:
            pkg_args.append("tests")
        if targets["scripts"]:
            pkg_args.append("tests/scripts")
        if targets["brand"]:
            pkg_args.append("brand")
        code, _ = run_cmd(["uv", "run", "pytest", "-q"] + pkg_args)
        if code != 0:
            failed = True
        print()

        if targets["python_packages"]:
            print("[3/4] mypy (touched packages)")
            code, _ = run_cmd(["uv", "run", "mypy"] + sorted(targets["python_packages"]))
            if code != 0:
                failed = True
            print()

    if targets["studio"]:
        print("[4/4] vitest (touched studio files)")
        code, _ = run_cmd(["npm", "--prefix", STUDIO_DIR, "test", "--", "--run"])
        if code != 0:
            failed = True
        print()
    else:
        print("[3/4] mypy (no Python packages touched) - skipped")
        print("[4/4] vitest (no studio files touched) - skipped")
        print()

    print("Skipped tiers: --full runs website, studio build, e2e")
    print("not run: coverage, e2e, website, desktop")
    print()
    if failed:
        print("FAILED")
        return 1
    print("PASSED (--default)")
    return 0


def verify_full(base: str = "origin/main", head: str = "HEAD") -> int:
    print("Tier: --full (CI's responsibility)")
    print("Budget: full matrix as in .agents/workflows/test.md; per-job budgets 5-20 min")
    print()
    failed = False

    print("[1/5] pytest (all)")
    code, _ = run_cmd(["uv", "run", "pytest"])
    if code != 0:
        failed = True
    print()

    print("[2/5] website pytest")
    code, _ = run_cmd(["uv", "run", "--directory", WEBSITE_DIR, "pytest", "tests/"])
    if code != 0:
        failed = True
    print()

    print("[3/5] studio vitest")
    code, _ = run_cmd(["npm", "--prefix", STUDIO_DIR, "test", "--", "--run"])
    if code != 0:
        failed = True
    print()

    print("[4/5] studio build")
    code, _ = run_cmd(["npm", "--prefix", STUDIO_DIR, "run", "build"])
    if code != 0:
        failed = True
    print()

    print("[5/5] studio e2e")
    code, _ = run_cmd(["npm", "--prefix", STUDIO_DIR, "run", "test:e2e"])
    if code != 0:
        failed = True
    print()

    print("not run: coverage (enforced in CI), desktop (not in this matrix)")
    print()
    if failed:
        print("FAILED")
        return 1
    print("PASSED (--full)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Focused verification gate")
    parser.add_argument("--changed", action="store_true", help="Fast gate on changed files")
    parser.add_argument(
        "--default", action="store_true", help="Adds mypy and vitest for touched areas"
    )
    parser.add_argument("--full", action="store_true", help="Full matrix (CI's job)")
    parser.add_argument("--base", default="origin/main", help="Base ref for diff")
    parser.add_argument("--head", default="HEAD", help="Head ref for diff")
    args = parser.parse_args(argv)

    if args.changed and not args.default and not args.full:
        return verify_changed(args.base, args.head)
    elif args.default and not args.changed and not args.full:
        return verify_default(args.base, args.head)
    elif args.full and not args.changed and not args.default:
        return verify_full(args.base, args.head)
    elif args.changed:
        return verify_changed(args.base, args.head)
    elif args.default:
        return verify_default(args.base, args.head)
    elif args.full:
        return verify_full(args.base, args.head)
    else:
        # default behavior
        parser.print_help()
        print("\nTip: --changed fits 10-30 minute agent budget; --full is CI's responsibility.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
