import socket
import sys
from pathlib import Path

from scripts import dev as run
from scripts.dev import is_port_in_use


def test_is_port_in_use_detects_bound_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        s.listen(1)
        port = s.getsockname()[1]

        assert is_port_in_use(port) is True


def test_is_port_in_use_returns_false_for_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]

    assert is_port_in_use(port) is False


def test_ports_are_mcp_and_sidecar():
    assert run.MCP_PORT == 8000
    assert run.STUDIO_PORT == 8100


def test_build_commands_exposes_mcp_and_sidecar():
    mcp, sidecar = run.build_commands()

    assert mcp == [sys.executable, "-m", "agentic_odi_mcp_server"]
    assert "uvicorn" in sidecar
    assert "agentic_odi_studio_api.app:create_app" in sidecar
    assert "--factory" in sidecar
    assert str(run.STUDIO_PORT) in sidecar


def test_spa_build_hint_points_at_studio_package():
    assert "npm" in run.SPA_BUILD_HINT
    assert "studio" in run.SPA_BUILD_HINT


def test_launcher_no_longer_references_streamlit():
    source = Path(run.__file__).read_text().lower()

    assert "streamlit" not in source
