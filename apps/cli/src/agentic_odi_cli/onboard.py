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
        domain: str | None = None,
        primary_user: str | None = None,
        business_model: str | None = None,
        core_problem: str | None = None,
        current_focus: str | None = None,
        confidence: float | None = None,
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
    "developer": 2,
    "error": 2,
    "tracking": 1,
    "monitoring": 1,
    "sentry": 2,
    "performance": 1,
    "analytics": 1,
    "optimization": 1,
    "saas": 2,
    "api": 2,
    "platform": 1,
    "infrastructure": 1,
    "security": 1,
    "auth": 1,
    "payment": 1,
    "ecommerce": 1,
    "retail": 1,
    "healthcare": 1,
    "finance": 1,
}

BUSINESS_MODEL_KEYWORDS = {
    "saas": "SaaS subscription",
    "subscription": "SaaS subscription",
    "api": "API usage-based",
    "usage": "API usage-based",
    "ecommerce": "E-commerce transaction",
    "retail": "E-commerce transaction",
    "marketplace": "Marketplace",
    "freemium": "Freemium",
    "enterprise": "Enterprise license",
}

PRIMARY_USER_KEYWORDS = {
    "developer": "Software developers",
    "dev": "Software developers",
    "engineer": "Software engineers",
    "engineering": "Software engineers",
    "devops": "DevOps engineers",
    "sre": "Site reliability engineers",
    "pm": "Product managers",
    "product": "Product managers",
    "designer": "Product designers",
    "data": "Data analysts",
    "analyst": "Data analysts",
    "marketing": "Marketing teams",
    "sales": "Sales teams",
    "support": "Customer support",
}

CONFIDENCE_THRESHOLD = 3


def _infer_from_text(text: str, keyword_map: dict[str, str]) -> tuple[str | None, float]:
    """Derive a value from text using keyword matching.

    Returns (value, confidence) where confidence is 0.0-1.0.
    """
    lowered = text.lower()
    best_match: str | None = None
    best_score = 0
    for keyword, value in keyword_map.items():
        count = lowered.count(keyword)
        if count:
            score = count
            if score > best_score:
                best_score = score
                best_match = value
    if best_match is None:
        return None, 0.0
    # Confidence: cap at 1.0 based on score relative to threshold
    confidence = min(best_score / float(CONFIDENCE_THRESHOLD), 1.0)
    return best_match, confidence


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
    confidence = min(scores[top_keyword] / float(CONFIDENCE_THRESHOLD), 1.0) if top_keyword else 0.0

    domain = signals.domain or ""

    # Infer primary_user, business_model, core_problem, current_focus from text
    primary_user, pu_conf = _infer_from_text(text, PRIMARY_USER_KEYWORDS)
    business_model, bm_conf = _infer_from_text(text, BUSINESS_MODEL_KEYWORDS)

    # core_problem from the title (stripped of common suffixes)
    core_problem = None
    if signals.title:
        cp = signals.title.strip()
        for suffix in (" | ", " - ", " — ", " : "):
            if suffix in cp:
                cp = cp.split(suffix)[0].strip()
                break
        core_problem = cp if cp else None

    # current_focus is the top domain keyword
    current_focus = top_keyword if top_keyword else None

    return profile.Baseline(
        schema_version=1,
        source="url",
        product_name=None,
        product_url=None,
        domain=domain,
        primary_user=primary_user,
        business_model=business_model,
        core_problem=core_problem,
        current_focus=current_focus,
        confidence=confidence,
        inferred=True,
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
    low_confidence = baseline.confidence is not None and baseline.confidence < 0.5
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
        confidence=0.3 if low_confidence else 0.0,
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

    return PageSignals(
        title=title,
        meta_description=meta_description,
        domain=domain,
        primary_user=None,
        business_model=None,
        core_problem=None,
        current_focus=None,
        confidence=0.0,
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
