"""Interactive /connect wizard for configuring the LLM provider and MCP server."""

from __future__ import annotations

import getpass

import typer

from agentic_odi_cli.chat import ChatConfig
from agentic_odi_cli.profile import LLMProfile, save_llm_profile

# ---------------------------------------------------------------------------
# Provider presets
# ---------------------------------------------------------------------------

_PRESETS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-opus-4-5",
    },
    "local": {
        "base_url": "http://localhost:8001/v1",
        "model": "local-tools-model",
    },
}

_VALID_PROVIDERS = list(_PRESETS.keys()) + ["other"]
_PROVIDER_PROMPT = "Provider [openai/anthropic/local/other]"


def run_connect_wizard(current_config: ChatConfig) -> ChatConfig | None:
    """Walk the user through LLM provider and MCP configuration interactively.

    Args:
        current_config: The currently active :class:`ChatConfig` used as
            defaults when the user presses Enter without typing a value.

    Returns:
        A new :class:`ChatConfig` built from the wizard's answers, or ``None``
        if the user cancelled with Ctrl-C.
    """
    try:
        # ------------------------------------------------------------------
        # Step 1 — Provider
        # ------------------------------------------------------------------
        provider = typer.prompt(_PROVIDER_PROMPT, default="local").strip().lower()
        if provider not in _VALID_PROVIDERS:
            # Unrecognised provider — treat as "other"
            provider = "other"

        preset = _PRESETS.get(provider)

        # ------------------------------------------------------------------
        # Step 2 — Base URL
        # ------------------------------------------------------------------
        default_url = (preset["base_url"] if preset else current_config.base_url) or ""
        base_url = typer.prompt("Base URL", default=default_url).strip() or default_url

        # ------------------------------------------------------------------
        # Step 3 — API Key (hidden)
        # ------------------------------------------------------------------
        raw_key = getpass.getpass("API key (hidden): ").strip()
        api_key = raw_key if raw_key else (current_config.api_key or "")

        # ------------------------------------------------------------------
        # Step 4 — Model
        # ------------------------------------------------------------------
        default_model = (preset["model"] if preset else current_config.model) or ""
        model = typer.prompt("Model", default=default_model).strip() or default_model

        # ------------------------------------------------------------------
        # Step 5 — MCP URL
        # ------------------------------------------------------------------
        default_mcp = current_config.mcp_url or ""
        mcp_url = typer.prompt("MCP server URL", default=default_mcp).strip() or default_mcp

        # ------------------------------------------------------------------
        # Step 6 — Summary + save
        # ------------------------------------------------------------------
        typer.echo("")
        typer.echo(f"  Provider : {provider}")
        typer.echo(f"  Base URL : {base_url}")
        typer.echo(f"  Model    : {model}")
        typer.echo(f"  MCP URL  : {mcp_url}")
        typer.echo("")

        if typer.confirm("Save to profile?", default=True):
            save_llm_profile(
                LLMProfile(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    mcp_url=mcp_url,
                    provider_label=provider,
                )
            )

    except KeyboardInterrupt:
        typer.echo("\nWizard cancelled.")
        return None

    return ChatConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        mcp_url=mcp_url,
    )
