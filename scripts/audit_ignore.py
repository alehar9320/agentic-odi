"""The accepted-advisory ledger the dependency audit reads (#1090).

The `dependencies` CI job runs `pip-audit`, `npm audit`, and `cargo audit`. An
advisory that is accepted rather than fixed has to be recorded somewhere with an
end date, or it becomes permanent by silence. `security/audit-ignore.toml` is
that record: one entry per accepted advisory, each with the package it affects,
why it is accepted, and an `expires` date no more than 90 days out.

This module is both the parser and the gate. It parses the ledger by hand
(``tomllib`` is 3.11+, and the test matrix still runs 3.10), validates every
entry, and turns the ledger into the arguments the audit tools understand:

- ``--check`` fails when an entry is expired, malformed, or dated too far out.
- ``--pip-args`` prints ``--ignore-vuln <id>`` for each entry.
- ``--cargo-args`` prints ``--ignore <id>`` for each entry.
- ``--npm-json`` reads ``npm audit --json`` and exits non-zero only for a
  high-or-critical advisory that no entry covers.

Run it locally with ``uv run python scripts/audit_ignore.py --check``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "security" / "audit-ignore.toml"

#: An accepted advisory may not outlive this window. A date further out is the
#: mechanism by which an ignore becomes permanent, so it is an error, not a
#: warning.
MAX_DAYS = 90

#: The severities `npm audit` reports that this gate blocks on.
NPM_BLOCKING_SEVERITIES = frozenset({"high", "critical"})

_TABLE = re.compile(r"^\[\[ignore\]\]\s*$")
_KV = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"\s*$')
_REQUIRED = ("id", "package", "reason", "expires")


@dataclass(frozen=True)
class Entry:
    """One accepted advisory and the date the acceptance lapses."""

    id: str
    package: str
    reason: str
    expires: date


def _strip_comment(line: str) -> str:
    """Drop a trailing comment, but only outside a quoted value."""
    in_string = False
    for index, char in enumerate(line):
        if char == '"':
            in_string = not in_string
        elif char == "#" and not in_string:
            return line[:index]
    return line


def parse_ledger(text: str) -> list[Entry]:
    """Parse ``[[ignore]]`` tables of string key/value pairs.

    Only the shape this ledger uses is supported: array-of-tables, one string
    per key, no nesting. Anything else raises, so a malformed ledger fails
    loudly instead of being read as an empty one.
    """
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if _TABLE.match(line):
            current = {}
            entries.append(current)
            continue
        match = _KV.match(line)
        if match is None:
            raise ValueError(f'line {lineno}: not a [[ignore]] table or key = "value": {raw!r}')
        if current is None:
            raise ValueError(f"line {lineno}: key outside an [[ignore]] table: {raw!r}")
        current[match.group(1)] = match.group(2)

    parsed: list[Entry] = []
    for index, table in enumerate(entries, start=1):
        missing = [key for key in _REQUIRED if key not in table]
        if missing:
            raise ValueError(f"[[ignore]] #{index} is missing {missing}")
        try:
            expires = date.fromisoformat(table["expires"])
        except ValueError as exc:
            raise ValueError(f"[[ignore]] #{index} has an unparseable expires: {exc}") from exc
        parsed.append(
            Entry(
                id=table["id"],
                package=table["package"],
                reason=table["reason"],
                expires=expires,
            )
        )
    return parsed


def validate(entries: list[Entry], today: date, max_days: int = MAX_DAYS) -> list[str]:
    """Every reason the ledger is not currently honest. Empty means it is."""
    issues: list[str] = []
    seen: set[str] = set()
    horizon = today + timedelta(days=max_days)
    for entry in entries:
        if not entry.id or not entry.package or not entry.reason:
            issues.append(f"{entry.id or '<no id>'}: id, package, and reason are all required")
        if entry.id in seen:
            issues.append(f"{entry.id}: listed more than once")
        seen.add(entry.id)
        if entry.expires < today:
            issues.append(f"{entry.id}: expired on {entry.expires.isoformat()}")
        elif entry.expires > horizon:
            issues.append(
                f"{entry.id}: expires {entry.expires.isoformat()}, more than {max_days} days out"
            )
    return issues


def load(path: Path = LEDGER) -> list[Entry]:
    return parse_ledger(path.read_text(encoding="utf-8"))


def _ghsa_ids(via: object) -> set[str]:
    """The GHSA ids in an advisory's ``via`` list, ignoring the string form.

    A ``via`` entry is either a string (a name the package is affected through)
    or an object with a ``url`` that names the advisory.
    """
    ids: set[str] = set()
    if not isinstance(via, list):
        return ids
    for item in via:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if isinstance(url, str) and "/" in url:
            ids.add(url.rsplit("/", 1)[-1])
    return ids


def unignored_npm_advisories(json_text: str, entries: list[Entry]) -> list[str]:
    """High-or-critical ``npm audit`` advisories the ledger does not cover.

    ``npm audit`` has no per-advisory ignore flag, so the gate filters its JSON
    itself. A package with several ``via`` entries is reported once per unignored
    id, so the failure names what to fix or accept.
    """
    ignored = {entry.id for entry in entries}
    data = json.loads(json_text)
    remaining: list[str] = []
    for name, report in sorted(data.get("vulnerabilities", {}).items()):
        if not isinstance(report, dict):
            continue
        if report.get("severity") not in NPM_BLOCKING_SEVERITIES:
            continue
        ids = _ghsa_ids(report.get("via"))
        if not ids:
            remaining.append(f"{name}: {report.get('severity')} advisory with no GHSA id")
            continue
        for advisory in sorted(ids - ignored):
            remaining.append(f"{name}: {advisory}")
    return remaining


def _print_issues(issues: list[str]) -> None:
    for issue in issues:
        print(f"::error::{issue}" if _in_actions() else f"error: {issue}", file=sys.stderr)


def _in_actions() -> bool:
    import os

    return os.environ.get("GITHUB_ACTIONS") == "true"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument(
        "--check", action="store_true", help="fail on an expired or malformed entry"
    )
    parser.add_argument(
        "--pip-args", action="store_true", help="print pip-audit --ignore-vuln args"
    )
    parser.add_argument("--cargo-args", action="store_true", help="print cargo audit --ignore args")
    parser.add_argument("--npm-json", type=Path, help="an `npm audit --json` report to filter")
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD), for tests")
    args = parser.parse_args(argv)

    try:
        entries = load(args.ledger)
    except (OSError, ValueError) as exc:
        _print_issues([f"cannot read {args.ledger}: {exc}"])
        return 1

    today = date.fromisoformat(args.today) if args.today else date.today()

    if args.check:
        issues = validate(entries, today)
        if issues:
            _print_issues(issues)
            return 1
        print(f"OK: {len(entries)} accepted advisories, none expired")

    if args.pip_args:
        print(" ".join(f"--ignore-vuln {entry.id}" for entry in entries))

    if args.cargo_args:
        print(" ".join(f"--ignore {entry.id}" for entry in entries))

    if args.npm_json:
        try:
            report = args.npm_json.read_text(encoding="utf-8")
        except OSError as exc:
            _print_issues([f"cannot read {args.npm_json}: {exc}"])
            return 1
        remaining = unignored_npm_advisories(report, entries)
        if remaining:
            _print_issues([f"npm advisory not in the ledger: {item}" for item in remaining])
            return 1
        print("OK: no unignored high or critical npm advisories")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
