"""Profile model, XDG config path, atomic load/save, and `setup`/`profile` Typer sub-app."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import typer

app = typer.Typer(name="profile", help="Profile management commands")

BASELINE_FILE_NAME = "baseline.json"


@dataclass
class Baseline:
    schema_version: int = 1
    created_at: str | None = None
    source: str | None = None
    product_name: str | None = None
    product_url: str | None = None
    domain: str | None = None
    primary_user: str | None = None
    business_model: str | None = None
    core_problem: str | None = None
    current_focus: str | None = None
    confidence: str | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "source": self.source,
            "product_name": self.product_name,
            "product_url": self.product_url,
            "domain": self.domain,
            "primary_user": self.primary_user,
            "business_model": self.business_model,
            "core_problem": self.core_problem,
            "current_focus": self.current_focus,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Baseline:
        kwargs = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**kwargs)


def config_dir() -> Path:
    """Return the XDG config dir for agentic-odi.

    Uses XDG_CONFIG_HOME if set; otherwise falls back to HOME/agentic-odi.
    """
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "agentic-odi"
    home = Path(os.getenv("HOME", ""))
    return home / "agentic-odi"


def baseline_file() -> Path:
    """Return the path to the baseline JSON file."""
    return config_dir() / BASELINE_FILE_NAME


def baseline_exists() -> bool:
    """Return True if the baseline file exists and is parseable."""
    return baseline_file().exists()


def load_baseline() -> Baseline | None:
    """Load the baseline file, returning None if it does not exist.

    Raises ValueError on unparseable JSON.
    """
    if not baseline_exists():
        return None
    try:
        with open(baseline_file()) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Failed to parse baseline file: {e}") from e
    return Baseline.from_dict(data)


def save_baseline(b: Baseline) -> Path:
    """Save the baseline atomically, setting created_at ISO-8601 UTC when None."""
    cfg_dir = config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    b = (
        b
        if b.created_at is not None
        else Baseline(
            **{k: v for k, v in b.to_dict().items() if k != "created_at"},
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    )
    target = baseline_file()
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w") as f:
        f.write(json.dumps(b.to_dict()))
    os.replace(tmp, target)
    return target


def backup_baseline() -> Path | None:
    """Copy the existing baseline file to a dated backup.

    Returns the path of the backup file, or None if no existing file.
    """
    if not baseline_exists():
        return None
    import shutil

    backup_path = baseline_file().with_name(
        f"baseline.json.bak-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    shutil.copy2(baseline_file(), backup_path)
    return backup_path


# ---------------------------------------------------------------------------
# LLM Profile
# ---------------------------------------------------------------------------

LLM_PROFILE_FILE_NAME = "llm_profile.json"


@dataclass
class LLMProfile:
    """Persisted LLM connection settings for the interactive chat."""

    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    mcp_url: str | None = None
    provider_label: str | None = None
    schema_version: int = 1
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "model": self.model,
            "mcp_url": self.mcp_url,
            "provider_label": self.provider_label,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LLMProfile:
        kwargs = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**kwargs)


def llm_profile_file() -> Path:
    """Return the path to the LLM profile JSON file."""
    return config_dir() / LLM_PROFILE_FILE_NAME


def llm_profile_exists() -> bool:
    """Return True if the LLM profile file exists."""
    return llm_profile_file().exists()


def load_llm_profile() -> LLMProfile | None:
    """Load the LLM profile file, returning None if it does not exist.

    Raises ValueError on unparseable JSON.
    """
    if not llm_profile_exists():
        return None
    try:
        with open(llm_profile_file()) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Failed to parse LLM profile file: {e}") from e
    return LLMProfile.from_dict(data)


def load_llm_config_dict() -> dict[str, str]:
    """Return persisted LLM config as a plain dict for use by any package.

    Returns an empty dict if no profile exists or parsing fails.
    Keys: base_url, api_key, model, mcp_url (only non-None values included).
    """
    try:
        p = load_llm_profile()
    except (ValueError, OSError):
        return {}
    if p is None:
        return {}
    result: dict[str, str] = {}
    for field in ("base_url", "api_key", "model", "mcp_url"):
        val = getattr(p, field, None)
        if val is not None:
            result[field] = val
    return result


def save_llm_profile(p: LLMProfile) -> Path:
    """Save the LLM profile atomically.

    Sets ``updated_at`` to UTC ISO-8601 on every save.
    Sets ``created_at`` if it is currently None.
    """
    cfg_dir = config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    d = p.to_dict()
    if d["created_at"] is None:
        d["created_at"] = now
    d["updated_at"] = now
    target = llm_profile_file()
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w") as f:
        f.write(json.dumps(d))
    os.replace(tmp, target)
    return target


# ---------------------------------------------------------------------------
# Typer Commands for profile & setup
# ---------------------------------------------------------------------------


@app.command("show")
def show_profile(as_json: bool = typer.Option(False, "--json", help="Format output as JSON")) -> None:
    """Show current product baseline profile."""
    b = load_baseline()
    if b is None:
        if as_json:
            typer.echo(json.dumps({}))
        else:
            typer.echo("No profile configured. Run 'agentic-odi setup' to create one.")
        return
    if as_json:
        typer.echo(json.dumps(b.to_dict(), indent=2))
        return
    typer.echo(f"Product Name: {b.product_name or ''}")
    typer.echo(f"Product URL:  {b.product_url or ''}")
    typer.echo(f"Domain:       {b.domain or ''}")
    typer.echo(f"Primary User: {b.primary_user or ''}")
    typer.echo(f"Business:     {b.business_model or ''}")
    typer.echo(f"Core Problem: {b.core_problem or ''}")
    typer.echo(f"Focus:        {b.current_focus or ''}")
    typer.echo(f"Confidence:   {b.confidence or ''}")


@app.command("path")
def path_cmd() -> None:
    """Print path to the baseline profile JSON file."""
    typer.echo(str(baseline_file()))


@app.command("set")
def set_profile(
    product_name: str | None = typer.Option(None, help="Product name"),
    domain: str | None = typer.Option(None, help="Domain"),
    primary_user: str | None = typer.Option(None, help="Primary user persona"),
    business_model: str | None = typer.Option(None, help="Business model"),
    core_problem: str | None = typer.Option(None, help="Core problem solved"),
    current_focus: str | None = typer.Option(None, help="Current focus"),
) -> None:
    """Set profile values non-interactively."""
    b = load_baseline() or Baseline(schema_version=1, source="cli")
    if product_name is not None:
        b.product_name = product_name
    if domain is not None:
        b.domain = domain
    if primary_user is not None:
        b.primary_user = primary_user
    if business_model is not None:
        b.business_model = business_model
    if core_problem is not None:
        b.core_problem = core_problem
    if current_focus is not None:
        b.current_focus = current_focus
    p = save_baseline(b)
    typer.echo(f"Profile saved to {p}")


def setup_wizard() -> None:
    """Run interactive baseline setup wizard."""
    typer.echo("Agentic ODI — Product Baseline Setup Wizard")
    typer.echo("==========================================")
    existing = load_baseline() or Baseline()

    p_name = typer.prompt("Product Name", default=existing.product_name or "")
    domain = typer.prompt("Domain", default=existing.domain or "")
    p_user = typer.prompt("Primary User", default=existing.primary_user or "")
    b_model = typer.prompt("Business Model", default=existing.business_model or "")
    c_prob = typer.prompt("Core Problem", default=existing.core_problem or "")
    c_focus = typer.prompt("Current Focus", default=existing.current_focus or "")

    b = Baseline(
        schema_version=1,
        source="wizard",
        product_name=p_name or None,
        domain=domain or None,
        primary_user=p_user or None,
        business_model=b_model or None,
        core_problem=c_prob or None,
        current_focus=c_focus or None,
        confidence="high",
    )
    p = save_baseline(b)
    typer.echo(f"Baseline configured successfully and saved to {p}")
