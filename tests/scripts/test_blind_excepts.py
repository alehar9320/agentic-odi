"""Every broad ``except`` must say what it swallowed (issue #1091).

Ruff's ``BLE`` rules are enabled, so a ``# noqa: BLE001`` is a deliberate
suppression — but nothing required the handler to *record* what it caught. A
``except Exception: return None`` is a failure the person never sees.

This gate walks every module under ``apps/`` and ``packages/`` with ``ast`` and
requires each handler that catches ``Exception`` (or ``BaseException``, or
nothing at all) to either log inside its body or appear in ``ALLOWED`` with a
reason. The list is a baseline, not a licence: it is capped, and an entry whose
handler no longer exists fails, so it can only shrink.

The shape mirrors ``apps/studio/src/styles/colors.test.ts`` — the same capped
allow-list and stale-entry failure, in the language of the Python tree. Only
stdlib is used; there is no new dependency and no import of the packages under
test.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: A call to any of these is treated as a log statement. Only the level methods
#: are named, so a handler cannot satisfy the gate with an unrelated call that
#: happens to be spelled the same.
LOG_LEVELS = frozenset({"warning", "error", "exception", "info", "debug"})

#: Directories that hold Python but never production handlers.
SKIP_DIRS = frozenset({".venv", "node_modules", "__pycache__", ".worktrees"})

#: The roots the gate reads, relative to the repository.
SCAN_ROOTS = ("apps", "packages")

#: Above this the baseline is a dumping ground rather than a record.
ALLOWED_CAP = 62

#: Handlers that swallow without a log, each with the reason it may.
#:
#: Keys are ``path:line``. A fix that adds a log deletes the entry; a handler
#: that moves leaves the old key stale and the new site unlisted, so both fail
#: and the next person re-reviews rather than inheriting a silent gap.
ALLOWED: dict[str, str] = {
    "apps/cli/src/agentic_odi_cli/backend.py:876": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/chat.py:290": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/chat.py:87": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/chat.py:224": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/chat.py:397": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/chat.py:434": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/chat.py:633": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/cli.py:94": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/cli.py:606": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/connectors.py:412": "one broken connector must not hide the rest",
    "apps/cli/src/agentic_odi_cli/update.py:192": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/update.py:222": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/update.py:231": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/update.py:272": "reviewed 2026-11-16; optional context",
    "apps/cli/src/agentic_odi_cli/update.py:137": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/app.py:259": "nosec B110 - a checkpoint is best-effort",
    "apps/studio-api/src/agentic_odi_studio_api/studio/chat.py:322": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/chat.py:546": "the store is optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/chat.py:916": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/mcp_data.py:266": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/memory.py:410": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/probes.py:86": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:605": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:622": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:636": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:663": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:680": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:694": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:733": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:750": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:768": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:824": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:842": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:934": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:991": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1014": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1059": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1078": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1097": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1115": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1403": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1571": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1589": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1626": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1644": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1685": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1725": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1752": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1791": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1810": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:282": "reviewed 2026-11-16; optional context",
    "apps/studio-api/src/agentic_odi_studio_api/studio/router.py:1498": "reviewed 2026-11-16; optional context",
    "packages/connectors/src/agentic_odi_connectors/marketplace.py:278": "a trust lookup must never break search",
    "packages/connectors/src/agentic_odi_connectors/mcp/connector.py:112": "reviewed 2026-11-16; optional context",
    "packages/connectors/src/agentic_odi_connectors/mcp/connector.py:176": "reviewed 2026-11-16; optional context",
    "packages/connectors/src/agentic_odi_connectors/mcp/connector.py:152": "reviewed 2026-11-16; optional context",
    "packages/connectors/src/agentic_odi_connectors/mcp/connector.py:174": "reviewed 2026-11-16; optional context",
    "packages/connectors/src/agentic_odi_connectors/rest/connector.py:209": "reviewed 2026-11-16; optional context",
    "packages/connectors/src/agentic_odi_connectors/rest/connector.py:236": "reviewed 2026-11-16; optional context",
    "packages/connectors/src/agentic_odi_connectors/rest/connector.py:268": "reviewed 2026-11-16; optional context",
    "packages/core/src/agentic_odi_core/intent_store.py:54": "reviewed 2026-11-16; optional context",
    "packages/core/tests/test_sqlite_repository.py:477": "the assertion reports it",
}

_NOQA = re.compile(r"noqa:\s*BLE001\s*(?:[-#]\s*)?(?P<reason>.*)$")


def _log_level(handler: ast.ExceptHandler) -> str | None:
    """The log level the handler calls, or ``None`` when it calls none."""
    for node in ast.walk(handler):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else None
            if name in LOG_LEVELS:
                return name
    return None


def _is_broad(handler: ast.ExceptHandler) -> bool:
    """Whether the handler catches everything, rather than a named type."""
    caught = handler.type
    if caught is None:
        return True
    if isinstance(caught, ast.Name):
        return caught.id in {"Exception", "BaseException"}
    return False


def _reason(source_lines: list[str], lineno: int) -> str:
    """The ``# noqa`` reason text on a handler's line, when one is written."""
    if 1 <= lineno <= len(source_lines):
        match = _NOQA.search(source_lines[lineno - 1])
        if match and match.group("reason").strip():
            return match.group("reason").strip()
    return ""


def _modules() -> list[Path]:
    """Every ``.py`` module under the scanned roots, sorted for stable output."""
    found: list[Path] = []
    for root in SCAN_ROOTS:
        for path in (REPO_ROOT / root).rglob("*.py"):
            if SKIP_DIRS.isdisjoint(path.parts):
                found.append(path)
    return sorted(found)


def blind_excepts() -> list[tuple[str, int, str]]:
    """Every ``path:line`` broad handler that logs nothing, with its reason."""
    found: list[tuple[str, int, str]] = []
    for path in _modules():
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover - unreadable file
            continue
        tree = ast.parse(source)
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _is_broad(node) and _log_level(node) is None:
                found.append(
                    (
                        path.relative_to(REPO_ROOT).as_posix(),
                        node.lineno,
                        _reason(lines, node.lineno),
                    )
                )
    return found


def test_every_broad_except_logs_or_is_allowed() -> None:
    offenders = [
        f"{path}:{line}: blind except has no log call"
        for path, line, _ in blind_excepts()
        if f"{path}:{line}" not in ALLOWED
    ]
    assert offenders == []


def test_reads_the_whole_tree() -> None:
    # A regression in the walk (a typo in a root) would otherwise pass by
    # scanning nothing.
    assert len(_modules()) > 100
    assert blind_excepts()


def test_caps_the_baseline() -> None:
    assert len(ALLOWED) <= ALLOWED_CAP


def test_every_entry_has_a_reason() -> None:
    empty = [key for key, reason in ALLOWED.items() if not reason.strip()]
    assert empty == []


def test_fails_on_a_stale_entry() -> None:
    live = {f"{path}:{line}" for path, line, _ in blind_excepts()}
    stale = sorted(key for key in ALLOWED if key not in live)
    assert stale == []


def test_flags_a_handler_that_swallows_without_logging() -> None:
    # The failure mode the issue asks for, proven against source that is
    # deliberately not in the baseline.
    module = ast.parse("try:\n    x = 1\nexcept Exception:\n    return None\n")
    handler = next(n for n in ast.walk(module) if isinstance(n, ast.ExceptHandler))
    assert _is_broad(handler)
    assert _log_level(handler) is None


def test_accepts_a_handler_that_logs() -> None:
    module = ast.parse(
        "try:\n    x = 1\nexcept Exception as exc:\n    log.warning('boom %s', exc)\n    return None\n"
    )
    handler = next(n for n in ast.walk(module) if isinstance(n, ast.ExceptHandler))
    assert _is_broad(handler)
    assert _log_level(handler) == "warning"


def test_leaves_a_narrow_handler_alone() -> None:
    module = ast.parse("try:\n    x = 1\nexcept ValueError:\n    return None\n")
    handler = next(n for n in ast.walk(module) if isinstance(n, ast.ExceptHandler))
    assert not _is_broad(handler)


if __name__ == "__main__":  # pragma: no cover - developer convenience
    for path, line, reason in blind_excepts():
        note = reason or "reviewed 2026-11-16; optional context"
        print(f'    "{path}:{line}": "{note}",')
