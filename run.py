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

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def start_server() -> subprocess.Popen:
    print("▶  Starting MCP server on http://localhost:8000/mcp ...")
    return subprocess.Popen(
        [sys.executable, "my_server.py"],
        cwd=PROJECT_DIR,
    )


def start_client() -> subprocess.Popen:
    print("▶  Starting Streamlit client on http://localhost:8501 ...")
    return subprocess.Popen(
        ["streamlit", "run", "my_client.py", "--server.headless", "true"],
        cwd=PROJECT_DIR,
    )


def main():
    server = start_server()

    # Give the server a moment to bind its port before the client tries to connect
    time.sleep(2)

    client = start_client()

    print("\n✅ Both processes are running.")
    print("   MCP Server  → http://localhost:8000/mcp")
    print("   Streamlit   → http://localhost:8501")
    print("\n   Press Ctrl+C to stop both.\n")

    def shutdown(signum=None, frame=None):
        print("\n⏹  Shutting down...")
        client.terminate()
        server.terminate()
        try:
            client.wait(timeout=5)
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            client.kill()
            server.kill()
        print("✅ All processes stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Wait for either process to exit unexpectedly
    while True:
        rc_server = server.poll()
        rc_client = client.poll()

        if rc_server is not None:
            print(f"\n⚠️  Server exited unexpectedly (code {rc_server}). Stopping client.")
            shutdown()

        if rc_client is not None:
            print(f"\n⚠️  Client exited unexpectedly (code {rc_client}). Stopping server.")
            shutdown()

        time.sleep(1)


if __name__ == "__main__":
    main()
