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

    domain = signals.domain or ""

    return profile.Baseline(
        schema_version=1,
        source="url",
        product_name=signals.title or None,
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
        primary_user="product users and operators",
        business_model="software platform",
        core_problem="optimizing functional workflow execution",
        current_focus="onboarding and setup",
        confidence="low" if low_confidence else "high",
    ), low_confidence


def _extract_signals(html: str, url: str) -> PageSignals:
    """Extract signals from HTML using stdlib regex."""

    title = ""
    meta_description = ""

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

    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.hostname or "localhost"

    headings = [
        h.group(1).strip()
        for h in re.finditer(r"<h[12][^>]*>([^<]*)</h[12]>", html, re.IGNORECASE)
    ]

    text = (title + " " + meta_description + " " + " ".join(headings)).lower()

    scores = {}
    for keyword, weight in DOMAIN_KEYWORDS.items():
        count = text.count(keyword)
        if count:
            scores[keyword] = count * weight

    top_keyword = max(scores, key=lambda k: scores[k], default=None)
    confidence = "high" if top_keyword and scores[top_keyword] >= CONFIDENCE_THRESHOLD else "low"

    if any(k in text for k in ("developer", "engineer", "dev", "team", "code", "api")):
        primary_user = "software developers and engineering teams"
    elif any(k in text for k in ("product", "manager", "pm", "strategy")):
        primary_user = "product managers and strategy teams"
    else:
        primary_user = "product users and operators"

    if any(k in text for k in ("saas", "pricing", "plan", "subscription", "cloud", "platform")):
        business_model = "subscription SaaS"
    else:
        business_model = "software platform"

    if top_keyword:
        core_problem = f"optimizing {top_keyword} workflow execution"
    elif headings:
        core_problem = f"streamlining {headings[0]}"
    elif title:
        core_problem = f"improving {title}"
    else:
        core_problem = "optimizing core functional workflow execution"

    current_focus = f"improving {title}" if title else "onboarding and setup"

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
    """Skip first-run onboarding if conditions are met."""
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
