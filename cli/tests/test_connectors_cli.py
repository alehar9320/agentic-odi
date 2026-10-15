import re
from unittest.mock import patch

from typer.testing import CliRunner

from cli.cli import app

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _run(args):
    return CliRunner().invoke(app, args)


def test_connectors_help_lists_subcommands():
    out = ANSI.sub("", _run(["connectors", "--help"]).output)
    for cmd in ["list", "add", "health", "ingest"]:
        assert cmd in out


def test_add_then_list_roundtrip(tmp_path):
    cfg = str(tmp_path / "connectors.json")
    r = _run(
        ["connectors", "add", "mcp", "--name", "gong", "--url", "http://h/mcp", "--config", cfg]
    )
    assert r.exit_code == 0
    out = ANSI.sub("", _run(["connectors", "list", "--config", cfg]).output)
    assert "gong" in out


def test_list_empty(tmp_path):
    out = ANSI.sub("", _run(["connectors", "list", "--config", str(tmp_path / "none.json")]).output)
    assert "No connectors configured" in out


def test_health_uses_injected_connector(tmp_path):
    cfg = str(tmp_path / "connectors.json")
    _run(["connectors", "add", "mcp", "--name", "gong", "--url", "http://h/mcp", "--config", cfg])

    class Fake:
        async def health(self):
            from connectors import HealthStatus

            return HealthStatus(ok=True, detail="ok")

    with patch("cli.connectors.build_connector", return_value=Fake()):
        r = _run(["connectors", "health", "--name", "gong", "--config", cfg])
    assert r.exit_code == 0
    assert "ok" in ANSI.sub("", r.output)


def test_health_failure_sets_exit_code(tmp_path):
    cfg = str(tmp_path / "connectors.json")
    _run(["connectors", "add", "mcp", "--name", "gong", "--url", "http://h/mcp", "--config", cfg])

    class Fake:
        async def health(self):
            from connectors import HealthStatus

            return HealthStatus(ok=False, detail="unreachable")

    with patch("cli.connectors.build_connector", return_value=Fake()):
        r = _run(["connectors", "health", "--name", "gong", "--config", cfg])
    assert r.exit_code == 1
    assert "unreachable" in ANSI.sub("", r.output)


def test_ingest_uses_injected_connector(tmp_path):
    cfg = str(tmp_path / "connectors.json")
    _run(["connectors", "add", "mcp", "--name", "gong", "--url", "http://h/mcp", "--config", cfg])

    class Fake:
        async def ingest(self):
            from connectors import IngestBatch

            return IngestBatch(connector_name="gong", records=[], errors=[])

    with patch("cli.connectors.build_connector", return_value=Fake()):
        r = _run(["connectors", "ingest", "--name", "gong", "--config", cfg])
    assert r.exit_code == 0
    assert "0" in ANSI.sub("", r.output)
