"""The accepted-advisory ledger is the gate's memory (#1090).

`security/audit-ignore.toml` records the advisories the repository accepts rather
than fixes, and `scripts/audit_ignore.py` reads it three ways: to validate the
ledger, to build the audit tools' ignore arguments, and to filter `npm audit`,
which has no ignore flag. Each way can fail silently — an expired entry that is
never checked, an id that does not reach the tool, an npm advisory that is high
but not in the ledger — so each is locked here.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from scripts.audit_ignore import (
    MAX_DAYS,
    Entry,
    load,
    parse_ledger,
    unignored_npm_advisories,
    validate,
)

TODAY = date(2026, 11, 16)


def _entry(**overrides: object) -> Entry:
    fields = {
        "id": "GHSA-aaaa-bbbb-cccc",
        "package": "example",
        "reason": "accepted for the test",
        "expires": TODAY,
    }
    fields.update(overrides)
    return Entry(**fields)  # type: ignore[arg-type]


def test_the_committed_ledger_parses_and_validates() -> None:
    entries = load()

    assert entries, "the committed ledger is empty; the gate would accept anything"
    assert validate(entries, TODAY) == []


def test_parse_reads_every_ignore_table() -> None:
    text = """
    # a comment
    [[ignore]]
    id = "GHSA-1"   # trailing comment
    package = "one"
    reason = "why"
    expires = "2026-12-01"

    [[ignore]]
    id = "GHSA-2"
    package = "two"
    reason = "why not"
    expires = "2026-12-02"
    """

    entries = parse_ledger(text)

    assert [entry.id for entry in entries] == ["GHSA-1", "GHSA-2"]
    assert entries[0].expires == date(2026, 12, 1)


def test_parse_rejects_a_missing_key() -> None:
    with pytest.raises(ValueError, match="missing"):
        parse_ledger('[[ignore]]\nid = "GHSA-1"\npackage = "one"\nreason = "why"\n')


def test_parse_rejects_a_key_outside_a_table() -> None:
    with pytest.raises(ValueError, match="outside"):
        parse_ledger('id = "GHSA-1"\n')


def test_parse_rejects_an_unparseable_date() -> None:
    with pytest.raises(ValueError, match="expires"):
        parse_ledger('[[ignore]]\nid = "x"\npackage = "p"\nreason = "r"\nexpires = "soon"\n')


def test_an_expired_entry_fails() -> None:
    issues = validate([_entry(expires=date(2026, 11, 15))], TODAY)

    assert issues and "expired" in issues[0]


def test_an_entry_too_far_out_fails() -> None:
    far = TODAY + timedelta(days=MAX_DAYS + 1)

    issues = validate([_entry(expires=far)], TODAY)

    assert issues and "more than" in issues[0]


def test_an_entry_exactly_at_the_horizon_is_allowed() -> None:
    horizon = TODAY + timedelta(days=MAX_DAYS)

    assert validate([_entry(expires=horizon)], TODAY) == []


def test_a_duplicate_id_fails() -> None:
    issues = validate([_entry(), _entry()], TODAY)

    assert issues and "more than once" in issues[0]


def _npm_report(name: str, severity: str, advisory: str) -> str:
    return json.dumps(
        {
            "vulnerabilities": {
                name: {
                    "severity": severity,
                    "via": [{"url": f"https://github.com/advisories/{advisory}"}],
                }
            }
        }
    )


def test_a_high_advisory_not_in_the_ledger_fails() -> None:
    report = _npm_report("pdfjs-dist", "high", "GHSA-hq66-cqwq-w95j")

    remaining = unignored_npm_advisories(report, [])

    assert remaining == ["pdfjs-dist: GHSA-hq66-cqwq-w95j"]


def test_a_high_advisory_in_the_ledger_passes() -> None:
    report = _npm_report("pdfjs-dist", "high", "GHSA-hq66-cqwq-w95j")

    remaining = unignored_npm_advisories(report, [_entry(id="GHSA-hq66-cqwq-w95j")])

    assert remaining == []


def test_a_low_advisory_is_not_blocking() -> None:
    report = _npm_report("left-pad", "moderate", "GHSA-low0-low0-low0")

    assert unignored_npm_advisories(report, []) == []


def test_a_critical_advisory_is_blocking() -> None:
    report = _npm_report("bad", "critical", "GHSA-crit-ical-0001")

    assert unignored_npm_advisories(report, []) == ["bad: GHSA-crit-ical-0001"]
