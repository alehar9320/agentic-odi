"""First-run onboarding: page fetch, HTML signal extraction, confirmation card, typed fallback."""

from __future__ import annotations

import re
import sys

import httpx
import typer

from agentic_odi_cli import profile

# ── PageSignals ──────────────────────────────────────────────────────────────


class PageSignals:
    """Extracted signals from a fetched page."""

    __slots__ = (
        "title",
        "meta_description",
        "domain",
        "primary_user",
        "business_model",
        "core_problem",
        "current_focus",
        "confidence",
    )

    def __init__(
        self,
        title: str,
        meta_description: str,
        domain: str | None,
        primary_user: str | None,
        business_model: str | None,
        core_problem: str | None,
        current_focus: str | None,
        confidence: str | None,
    ) -> None:
        self.title = title
        self.meta_description = meta_description
        self.domain = domain
        self.primary_user = primary_user
        self.business_model = business_model
        self.core_problem = core_problem
        self.current_focus = current_focus
        self.confidence = confidence

    def __repr__(self) -> str:
        return f"PageSignals(title={self.title!r}, domain={self.domain!r}, confidence={self.confidence!r})"


# ── Keyword-based inference ─────────────────────────────────────────────────

DOMAIN_KEYWORDS: dict[str, int] = {
    "devtools": 3,
    "error": 2,
    "tracking": 1,
    "monitoring": 1,
    "sentry": 2,
    "performance": 1,
    "analytics": 1,
    "optimization": 1,
}

CONFIDENCE_THRESHOLD = 3


def infer_baseline(signals: PageSignals) -> tuple[profile.Baseline, dict[str, int]]:
    """Deterministic keyword-based inference from extracted page signals.

    Returns a Baseline and a dict of per-domain keyword scores.
    """
    scores: dict[str, int] = {}
    text = (signals.title or "") + " " + (signals.meta_description or "")
    for keyword, weight in DOMAIN_KEYWORDS.items():
        count = text.lower().count(keyword)
        if count:
            scores[keyword] = count * weight

    top_keyword = max(scores, key=lambda keyword: scores[keyword], default=None)
    confidence = "high" if top_keyword and scores[top_keyword] >= CONFIDENCE_THRESHOLD else "low"

    # Map domain from signals; fall back to empty string if none
    domain = signals.domain or ""

    return profile.Baseline(
        schema_version=1,
        source="url",
        product_name=None,
        product_url=None,
        domain=domain,
        primary_user=signals.primary_user,
        business_model=signals.business_model,
        core_problem=signals.core_problem,
        current_focus=signals.current_focus,
        confidence=confidence,
    ), scores


# ── URL signal fetching ─────────────────────────────────────────────────────

UA = "agentic-odi/0.1.0"


def fetch_signals(url: str, timeout: float = 8.0) -> tuple[profile.Baseline | PageSignals, bool]:
    """Fetch *url* and extract PageSignals.

    Returns (signals, low_confidence) where low_confidence=True means the
    inference confidence was "low" (≤2 keyword matches) — the caller should
    fall back to the typed path.
    """
    try:
        response = httpx.get(url, timeout=timeout, headers={"User-Agent": UA})
        response.raise_for_status()
    except Exception:  # noqa: BLE001 - any fetch failure falls back to the typed path
        # Fetch failure → typed path
        return _default_signals(low_confidence=True)

    signals = _extract_signals(response.text, str(response.url))
    baseline, scores = infer_baseline(signals)
    low_confidence = baseline.confidence == "low"
    return baseline, low_confidence


def _default_signals(low_confidence: bool = False) -> tuple[PageSignals, bool]:
    return PageSignals(
        title="",
        meta_description="",
        domain=None,
        primary_user=None,
        business_model=None,
        core_problem=None,
        current_focus=None,
        confidence="low" if low_confidence else "high",
    ), low_confidence


def _extract_signals(html: str, url: str) -> PageSignals:
    """Extract signals from HTML using stdlib html.parser."""

    title = ""
    meta_description = ""

    # Simple regex-based extraction (no external parser dependency)
    t = re.search(r"<title>([^<]*)</title>", html, re.IGNORECASE)
    if t:
        title = t.group(1).strip()

    m = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^>]*)["\']',
        html,
        re.IGNORECASE,
    )
    if m:
        meta_description = m.group(1).strip()

    # Very simple domain extraction from the URL
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.hostname or None

    # Simple primary_user and business_model extraction from title/meta
    # (placeholder: derive from title tokens)
    primary_user = None
    business_model = None
    core_problem = None
    current_focus = None

    # Compute confidence based on keyword scores
    scores = {}
    text = (title or "") + " " + (meta_description or "")
    for keyword, weight in DOMAIN_KEYWORDS.items():
        count = text.lower().count(keyword)
        if count:
            scores[keyword] = count * weight

    top_keyword = max(scores, key=lambda keyword: scores[keyword], default=None)
    confidence = "high" if top_keyword and scores[top_keyword] >= CONFIDENCE_THRESHOLD else "low"

    return PageSignals(
        title=title,
        meta_description=meta_description,
        domain=domain,
        primary_user=primary_user,
        business_model=business_model,
        core_problem=core_problem,
        current_focus=current_focus,
        confidence=confidence,
    )


# ── Confirmation card ───────────────────────────────────────────────────────

CARD_LINES: tuple[str, ...] = (
    "Based on the page you're visiting, we've detected the following:",
    "",
    "Product: <product_name>",
    "Problem: <core_problem>",
    "Business Model: <business_model>",
    "",
    "If this is correct, type the details below.",
    "Otherwise, type your inputs manually.",
    "",
    "Product name:",
    "Core problem:",
    "Business model:",
    "",
    "Type 'done' to accept these defaults, or press enter for the typed path.",
)

HONESTY_CONTRACT_LINES: tuple[str, ...] = (
    "(this is an experimental feature — no data is shared without your consent)",
    "we don't publish dates or send reminders",
    "open an issue if you have questions: https://github.com/alehar9320/agentic-odi/issues",
    "http://localhost:8000/mcp",  # MCP endpoint for maintainers",
)


# ── Public API ──────────────────────────────────────────────────────────────

__all__ = [
    "PageSignals",
    "infer_baseline",
    "fetch_signals",
    "CARD_LINES",
    "HONESTY_CONTRACT_LINES",
]


def maybe_run_first_launch(
    *, no_onboard: bool = False, invoked_subcommand: str | None = None
) -> None:
    """Skip first-run onboarding if conditions are met.

    Conditions that skip onboarding:
    - baseline already exists
    - no TTY (non-interactive: not stdin.isatty() or not stdout.isatty())
    - --no-onboard flag passed
    - invoked Subcommand is one that should not trigger onboarding
    """
    if no_onboard:
        return

    if profile.baseline_exists():
        return

    # Non-interactive contexts skip the card
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return

    # Do not trigger onboarding for specific subcommands
    if invoked_subcommand and invoked_subcommand in {"setup", "profile", "version", "help"}:
        return

    typer.echo("First-run onboarding card")
    typer.echo("=" * 60)
    for line in CARD_LINES:
        typer.echo(line)
    typer.echo("=" * 60)
    typer.echo("".join(HONESTY_CONTRACT_LINES))
    typer.echo("Run `agentic-odi setup` to configure your product baseline interactively.")
