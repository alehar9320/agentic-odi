"""
run.py — Local dev launcher for Agentic ODI
Starts the FastMCP server (my_server.py) and the Streamlit client (my_client.py)
concurrently. Shutting down this script (Ctrl+C) terminates both processes.

Usage:
    python run.py
"""

import subprocess
import sys
import os
import time
import signal
import socket

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MCP_PORT = 8000
CLIENT_PORT = 8501


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def start_server() -> subprocess.Popen:
    if is_port_in_use(MCP_PORT):
        print(f"Error: Port {MCP_PORT} is already in use.")
        print("Please stop any process running on this port and try again.")
        sys.exit(1)

    print(f"Starting MCP server on http://localhost:{MCP_PORT}/mcp ...")
    return subprocess.Popen(
        [sys.executable, "my_server.py"],
        cwd=PROJECT_DIR,
    )


def start_client() -> subprocess.Popen:
    if is_port_in_use(CLIENT_PORT):
        print(
            f"Warning: Port {CLIENT_PORT} is already in use. Streamlit might choose another port."
        )

    print(f"Starting Streamlit client on http://localhost:{CLIENT_PORT} ...")
    return subprocess.Popen(
        [
            "streamlit",
            "run",
            "my_client.py",
            "--server.headless",
            "true",
            "--server.port",
            str(CLIENT_PORT),
        ],
        cwd=PROJECT_DIR,
    )


def main():
    server = None
    client = None

    def shutdown(signum=None, frame=None):
        print("\nShutting down...")
        if client:
            client.terminate()
        if server:
            server.terminate()

        try:
            if client:
                client.wait(timeout=5)
            if server:
                server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if client:
                client.kill()
            if server:
                server.kill()

        print("✅ All processes stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        server = start_server()
        # Give the server a moment to bind its port before the client tries to connect
        time.sleep(2)
        client = start_client()

        print("\nBoth processes are running.")
        print(f"MCP Server  -> http://localhost:{MCP_PORT}/mcp")
        print(f"Streamlit   -> http://localhost:{CLIENT_PORT}")
        print("\nPress Ctrl+C to stop both.\n")

        # Wait for either process to exit unexpectedly
        while True:
            rc_server = server.poll()
            rc_client = client.poll()

            if rc_server is not None:
                print(f"\nServer exited unexpectedly (code {rc_server}).")
                break

            if rc_client is not None:
                print(f"\nClient exited unexpectedly (code {rc_client}).")
                break

            time.sleep(1)

    except Exception as e:
        print(f"\nError: {e}")
    finally:
        shutdown()


if __name__ == "__main__":
    main()
