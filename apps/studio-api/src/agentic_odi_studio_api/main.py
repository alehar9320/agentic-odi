"""Main entry for local server."""

import uvicorn


def main() -> None:
    uvicorn.run("agentic_odi_studio_api.app:create_app", factory=True, host="127.0.0.1", port=8100)


if __name__ == "__main__":
    main()
