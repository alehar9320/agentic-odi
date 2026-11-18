"""Profile model, XDG config path, atomic load/save, and `setup`/`profile` Typer sub-app."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(name="profile", help="Profile management commands")

BASELINE_FILE_NAME = "baseline.json"
BASELINE_BACKUP_KEEP = 5


class ProfileFileError(ValueError):
    """A profile file could not be read or parsed, with the reason named."""


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
    confidence: float | None = None
    inferred: bool = False

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
            "inferred": self.inferred,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Baseline:
        fields = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        unknown = sorted(k for k in d if k not in fields)
        if unknown:
            raise ValueError(
                f"Baseline.from_dict: unknown key(s) {unknown}; valid fields: {sorted(fields)}"
            )
        return cls(**{k: v for k, v in d.items() if k in fields})


_CLEARABLE_PROFILE_FIELDS = (
    "product_name",
    "domain",
    "primary_user",
    "business_model",
    "core_problem",
    "current_focus",
)


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

    Raises ProfileFileError on unreadable file or unparseable JSON.
    """
    if not baseline_exists():
        return None
    path = baseline_file()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise ProfileFileError(f"Could not read {path}: {exc.strerror or exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileFileError(
            f"{path} is not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from exc
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
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(b.to_dict()))
    os.replace(tmp, target)
    return target


def _backup_timestamp() -> str:
    """Return the fixed-width UTC stamp used to name baseline backups."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def prune_baseline_backups(keep: int = BASELINE_BACKUP_KEEP) -> list[Path]:
    """Delete all but the newest `keep` baseline backups.

    The stamp is fixed-width ISO, so lexical order is chronological. Returns the
    removed paths. A failed unlink is skipped rather than raised. `keep <= 0`
    disables retention and removes nothing.
    """
    if keep <= 0:
        return []
    backups = sorted(
        baseline_file().parent.glob(f"{BASELINE_FILE_NAME}.bak-*"),
        key=lambda p: p.name,
        reverse=True,
    )
    removed: list[Path] = []
    for stale in backups[keep:]:
        try:
            stale.unlink()
        except OSError:
            continue
        removed.append(stale)
    return removed


def backup_baseline() -> Path | None:
    """Copy the existing baseline file to a dated backup.

    Returns the path of the backup file, or None if no existing file.
    """
    if not baseline_exists():
        return None
    backup_path = baseline_file().with_name(f"{BASELINE_FILE_NAME}.bak-{_backup_timestamp()}")
    shutil.copy2(baseline_file(), backup_path)
    if BASELINE_BACKUP_KEEP > 0:
        prune_baseline_backups()
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

    Raises ProfileFileError on unreadable file or unparseable JSON.
    """
    if not llm_profile_exists():
        return None
    path = llm_profile_file()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise ProfileFileError(f"Could not read {path}: {exc.strerror or exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileFileError(
            f"{path} is not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from exc
    return LLMProfile.from_dict(data)


def load_llm_config_dict() -> dict[str, str]:
    """Return persisted LLM config as a plain dict for use by any package.

    Returns an empty dict if no profile exists or parsing fails.
    Keys: base_url, api_key, model, mcp_url (only non-None values included).

    This function deliberately swallows ProfileFileError (and OSError) because it feeds
    defaults to callers that expect graceful degradation rather than hard failures.
    """
    try:
        p = load_llm_profile()
    except (ProfileFileError, OSError):
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
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(d))
    os.replace(tmp, target)
    return target


# ---------------------------------------------------------------------------
# Typer Commands for profile & setup
# ---------------------------------------------------------------------------


def _profile_display_value(value: str | None) -> str:
    if value is None:
        return "—"
    if value == "":
        return "(empty)"
    return value


@app.command("show")
def show_profile(
    as_json: bool = typer.Option(False, "--json", help="Format output as JSON"),
) -> None:
    """Show current product baseline profile."""
    try:
        b = load_baseline()
    except ProfileFileError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if b is None:
        if as_json:
            typer.echo(json.dumps({}))
        else:
            typer.echo("No profile configured. Run 'agentic-odi setup' to create one.")
        return
    if as_json:
        typer.echo(json.dumps(b.to_dict(), indent=2))
        return
    typer.echo(f"Product Name: {_profile_display_value(b.product_name)}")
    typer.echo(f"Product URL:  {_profile_display_value(b.product_url)}")
    typer.echo(f"Domain:       {_profile_display_value(b.domain)}")
    typer.echo(f"Primary User: {_profile_display_value(b.primary_user)}")
    typer.echo(f"Business:     {_profile_display_value(b.business_model)}")
    typer.echo(f"Core Problem: {_profile_display_value(b.core_problem)}")
    typer.echo(f"Focus:        {_profile_display_value(b.current_focus)}")
    typer.echo(f"Confidence:   {b.confidence if b.confidence is not None else '—'}")


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
    clear: Annotated[
        list[str] | None,
        typer.Option(
            "--clear",
            help=(
                "Field to unset (repeatable): product_name, domain, primary_user, "
                "business_model, core_problem, current_focus"
            ),
        ),
    ] = None,
) -> None:
    """Set profile values non-interactively."""
    clear_fields = clear or []
    valid_clear_fields = _CLEARABLE_PROFILE_FIELDS
    for name in clear_fields:
        if name not in valid_clear_fields:
            typer.echo(
                f"Unknown field to clear: {name}. Valid names: {', '.join(valid_clear_fields)}",
                err=True,
            )
            raise typer.Exit(code=2)

    try:
        b = load_baseline() or Baseline(schema_version=1, source="cli")
    except ProfileFileError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
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
    # Apply --clear after set-options so `--core-problem x --clear core_problem` ends unset.
    for name in clear_fields:
        setattr(b, name, None)
    p = save_baseline(b)
    typer.echo(f"Profile saved to {p}")


def setup_wizard() -> None:
    """Run interactive baseline setup wizard."""
    typer.echo("Agentic ODI — Product Baseline Setup Wizard")
    typer.echo("==========================================")
    try:
        existing = load_baseline() or Baseline()
    except ProfileFileError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

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
    )
    p = save_baseline(b)
    typer.echo(f"Baseline configured successfully and saved to {p}")
