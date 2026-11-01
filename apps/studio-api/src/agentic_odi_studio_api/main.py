"""Main entry for local server.

The sidecar runs one uvicorn server in this process. uvicorn installs handlers
for ``SIGTERM`` (the signal the desktop shell sends when it quits) and
``SIGINT``; either runs the app's lifespan shutdown, which checkpoints each
SQLite store and closes it. That is what keeps a clean stop from leaving a
write-ahead log behind for the next process to recover.
"""

import uvicorn


def main() -> None:
    uvicorn.run("agentic_odi_studio_api.app:create_app", factory=True, host="127.0.0.1", port=8100)


if __name__ == "__main__":
    main()
