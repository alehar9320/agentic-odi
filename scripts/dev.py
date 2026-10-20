"""
Local dev launcher for Agentic ODI.

Starts the FastMCP server (``python -m agentic_odi_mcp_server``) and the Living
Studio sidecar (``uvicorn agentic_odi_studio_api.app:create_app --factory``)
concurrently, then prints the MCP and Studio URLs. Shutting down this script
(Ctrl+C) terminates both processes.

Usage:
    uv run python scripts/dev.py
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess  # nosec B404 - launches only fixed child commands (see B603 notes)
import sys
import time

MCP_PORT = 8000
STUDIO_PORT = 8100

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPA_DIST = os.environ.get(
    "AGENTIC_ODI_STUDIO_DIST", os.path.join(REPO_ROOT, "apps", "studio", "dist")
)
SPA_BUILD_HINT = (
    "Frontend not built — run `npm --prefix apps/studio run build` to serve the Studio UI."
)


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def build_commands() -> tuple[list[str], list[str]]:
    """Return the (mcp_server, sidecar) argv lists, both shell-free and fixed."""
    mcp_command = [sys.executable, "-m", "agentic_odi_mcp_server"]
    sidecar_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "agentic_odi_studio_api.app:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(STUDIO_PORT),
    ]
    return mcp_command, sidecar_command


def start_server() -> subprocess.Popen:
    if is_port_in_use(MCP_PORT):
        print(f"Error: Port {MCP_PORT} is already in use.")
        print("Please stop any process running on this port and try again.")
        sys.exit(1)

    mcp_command, _ = build_commands()
    print(f"Starting MCP server on http://localhost:{MCP_PORT}/mcp ...")
    # Fixed command, no shell, no untrusted input.
    return subprocess.Popen(mcp_command)  # nosec B603


def start_studio() -> subprocess.Popen:
    if is_port_in_use(STUDIO_PORT):
        print(f"Warning: Port {STUDIO_PORT} is already in use. The sidecar may fail to start.")

    _, sidecar_command = build_commands()
    print(f"Starting Living Studio sidecar on http://localhost:{STUDIO_PORT} ...")
    # Fixed command, no shell, no untrusted input.
    return subprocess.Popen(sidecar_command)  # nosec B603


def main() -> None:
    server = None
    studio = None

    def shutdown(signum=None, frame=None):
        print("\nShutting down...")
        if studio:
            studio.terminate()
        if server:
            server.terminate()

        try:
            if studio:
                studio.wait(timeout=5)
            if server:
                server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if studio:
                studio.kill()
            if server:
                server.kill()

        print("✅ All processes stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        server = start_server()
        # Give the server a moment to bind its port before the sidecar connects
        time.sleep(2)
        studio = start_studio()

        print("\nBoth processes are running.")
        print(f"MCP Server   -> http://localhost:{MCP_PORT}/mcp")
        print(f"Living Studio -> http://localhost:{STUDIO_PORT}")
        if not os.path.isdir(SPA_DIST):
            print(f"\n⚠️  {SPA_BUILD_HINT}")
        print("\nPress Ctrl+C to stop both.\n")

        # Wait for either process to exit unexpectedly
        while True:
            rc_server = server.poll()
            rc_studio = studio.poll()

            if rc_server is not None:
                print(f"\nServer exited unexpectedly (code {rc_server}).")
                break

            if rc_studio is not None:
                print(f"\nStudio sidecar exited unexpectedly (code {rc_studio}).")
                break

            time.sleep(1)

    except Exception as e:  # noqa: BLE001
        print(f"\nError: {e}")
    finally:
        shutdown()


if __name__ == "__main__":
    main()
