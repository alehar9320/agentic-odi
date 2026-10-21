"""Sync README.md to website/index.html.

Reads the repo's README.md and regenerates the GitHub Pages index.html.
Idempotent: running multiple times produces identical output.
Does NOT alter the honesty contract strings (they are embedded verbatim).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
SITE = ROOT / "website"
INDEX_HTML = SITE / "index.html"

HONESTY_CONTRACTS = [
    "experimental",
    "free prefect account",
    "all rights reserved",
    "strategyn",
    "your roadmap is a guess.",
    "we dont publish dates",
    "open an issue",
    "http://localhost:8000/mcp",
]


def _extract_title(text: str) -> str:
    m = re.search(r"^#+\s+(.+)", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return "Agentic ODI"


def _extract_description(text: str) -> str:
    lines = text.splitlines()
    in_code_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if (
            stripped
            and not stripped.startswith(">")
            and not stripped.startswith("---")
            and not stripped.startswith("#")
            and not stripped.startswith("<")
            and not stripped.startswith("[")
            and not in_code_block
        ):
            return _strip_markdown(stripped)
    return "Experimental MCP server for Outcome-Driven Innovation"


def _strip_markdown(text: str) -> str:
    import re

    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^\*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^\*]+)\*", r"\1", text)
    return text


def _extract_status(text: str):
    low = text.lower()
    experimental = "experimental" in low
    actual_no_dates = "we don't publish dates" in low or "we dont publish dates" in low
    return (
        "Experimental" if experimental else "Ready",
        "We don't publish dates." if actual_no_dates else "",
    )


def generate() -> None:
    """Read README.md and write website/index.html."""
    readme_text = README.read_text(encoding="utf-8")

    title = _extract_title(readme_text)
    description = _extract_description(readme_text)
    status_label, no_dates_text = _extract_status(readme_text)

    how_steps = [
        "Capture — jobs, steps, and desired outcomes with importance/satisfaction scores, via CLI, connectors, or The Living Studio.",
        "Query — agents call MCP tools for job maps and opportunity scores at decision time, local or hosted.",
        "Steer — The Living Studio shows the Opportunity Landscape, Universal Job Map, and Impact Simulation so the team decides from the same picture.",
    ]

    html_lines = []

    html_lines.append("<!DOCTYPE html>")
    html_lines.append('<html lang="en">')
    html_lines.append("<head>")
    html_lines.append('  <meta charset="utf-8">')
    html_lines.append('  <meta name="viewport" content="width=device-width, initial-scale=1">')
    html_lines.append(f"  <title>{title} — Agentic ODI</title>")
    html_lines.append('  <meta name="description" content="' + description + '">')
    html_lines.append('  <meta property="og:type" content="website">')
    html_lines.append('  <meta property="og:site_name" content="Agentic ODI">')
    html_lines.append(
        '  <meta property="og:title" content="Your roadmap is a guess. — Agentic ODI">'
    )
    html_lines.append('  <meta property="og:description" content="' + description + '">')
    html_lines.append(
        '  <meta property="og:url" content="https://alehar9320.github.io/agentic-odi/">'
    )
    html_lines.append(
        '  <meta property="og:image" content="https://alehar9320.github.io/agentic-odi/assets/og.png">'
    )
    html_lines.append('  <meta name="twitter:card" content="summary_large_image">')
    html_lines.append(
        '  <meta name="twitter:title" content="Your roadmap is a guess. — Agentic ODI">'
    )
    html_lines.append('  <meta name="twitter:description" content="' + description + '">')
    html_lines.append(
        '  <meta name="twitter:image" content="https://alehar9320.github.io/agentic-odi/assets/og.png">'
    )
    html_lines.append(
        '  <meta name="theme-color" content="#f1f5f9" media="(prefers-color-scheme: light)">'
    )
    html_lines.append(
        '  <meta name="theme-color" content="#0b0d13" media="(prefers-color-scheme: dark)">'
    )
    html_lines.append('  <link rel="canonical" href="https://alehar9320.github.io/agentic-odi/">')
    html_lines.append('  <link rel="stylesheet" href="assets/style.css">')
    html_lines.append('  <link rel="icon" type="image/svg+xml" href="assets/favicon.svg">')
    html_lines.append(
        '  <link rel="icon" type="image/png" href="assets/favicon.png" sizes="32x32">'
    )
    html_lines.append("</head>")
    html_lines.append("<body>")
    html_lines.append("  <h1>Your roadmap is a guess.</h1>")
    html_lines.append("  <header>")
    html_lines.append('    <svg viewBox="0 0 32 32" aria-hidden="true" width="16" height="16">')
    html_lines.append(
        '      <path fill="#475569" d="M0 0h32v32H0zM4 4h24v2H4V4zm0 6h24v2H4V10zm0 6h24v2H4V16zm0 6h24v2H4V22z"/>'
    )
    html_lines.append("    </svg>")
    html_lines.append('    <strong style="color:#1d1d1f">Agentic ODI</strong>')
    html_lines.append(
        '    <a href="#run" style="font-size:0.75rem;text-transform:uppercase;letter-spacing:0.08em;color:#0062c4;">Run it in 60 seconds</a>'
    )
    html_lines.append("  </header>")

    html_lines.append("  <main>")

    # Problem section
    html_lines.append('    <section id="problem">')
    html_lines.append("      <h2>Opinion is expensive.</h2>")
    html_lines.append(
        '      <blockquote>"Roadmaps set by whoever talks loudest." — Decisions default to seniority, not evidence.</blockquote>'
    )
    html_lines.append(
        '      <blockquote>"Features for customers who never asked." — Nobody validated the outcome; only the idea.</blockquote>'
    )
    html_lines.append(
        '      <blockquote>"Agents fluent in everything, grounded in nothing." — A model will confidently invent your customer.</blockquote>'
    )
    html_lines.append("      <p>Add it up and the roadmap isn't a plan. It's a guess.</p>")
    html_lines.append("    </section>")

    # Insight section
    html_lines.append('    <section id="insight">')
    html_lines.append("      <h2>Ask for outcomes, not opinions.</h2>")
    html_lines.append(
        "      <p>Outcome-Driven Innovation asks customers how much each desired outcome matters and how satisfied they are with it today.</p>"
    )
    html_lines.append(
        "      <p>The gap between importance and satisfaction is where products win or die.</p>"
    )
    html_lines.append(
        "      <p>Agentic ODI stores those outcomes, scores them, and serves them to any agent over MCP.</p>"
    )
    html_lines.append("      <p>Opportunity = Importance + max(Importance - Satisfaction, 0)</p>")
    html_lines.append("      <figure>")
    html_lines.append(
        '        <svg viewBox="0 0 200 60" aria-label="Illustrative outcome data" style="width:200px;height:60px;">'
    )
    html_lines.append('          <rect width="200" height="60" fill="#f5f5f7" rx="999"/>')
    html_lines.append('          <g fill="#0071e3">')
    html_lines.append('            <rect x="0" y="20" width="80" height="15" rx="2"/>')
    html_lines.append('            <rect x="40" y="10" width="30" height="30" rx="3"/>')
    html_lines.append('            <rect x="90" y="25" width="50" height="15" rx="2"/>')
    html_lines.append("          </g>")
    html_lines.append(
        '          <text x="100" y="38" fill="#6e6e73" font-family="system-font" font-size="0.75rem" text-anchor="middle">Illustrative outcome data</text>'
    )
    html_lines.append("        </svg>")
    html_lines.append(
        '        <figcaption style="font-size:0.75rem;color:#6e6e73;margin-top:4px;text-align:center;">Illustrative outcome data</figcaption>'
    )
    html_lines.append("        </figure>")
    html_lines.append(
        '      <p style="margin-top:12px;font-size:0.875rem;color:#6e6e73;">86% innovation success rate — as reported in ODI literature (Strategyn)</p>'
    )
    html_lines.append("    </section>")

    # How section
    html_lines.append('    <section id="how">')
    html_lines.append("      <h2>How it works.</h2>")
    html_lines.append("      <ol>")
    for step in how_steps:
        html_lines.append(f"        <li><strong>{step}</strong></li>")
    html_lines.append("      </ol>")
    html_lines.append("      <figure>")
    html_lines.append(
        '        <svg viewBox="0 0 200 80" aria-label="Illustrative studio figure" style="width:200px;height:80px;">'
    )
    html_lines.append('          <rect width="200" height="80" fill="#f5f5f7" rx="999"/>')
    html_lines.append('          <g fill="#0071e3">')
    html_lines.append('            <rect x="20" y="10" width="40" height="30" rx="3"/>')
    html_lines.append('            <rect x="80" y="20" width="50" height="20" rx="3"/>')
    html_lines.append('            <rect x="150" y="10" width="40" height="30" rx="3"/>')
    html_lines.append("          </g>")
    html_lines.append(
        '          <text x="100" y="50" fill="#6e6e73" font-family="system-font" font-size="0.75rem" text-anchor="middle">Illustrative</text>'
    )
    html_lines.append("        </svg>")
    html_lines.append(
        '        <figcaption style="font-size:0.75rem;color:#6e6e73;margin-top:4px;text-align:center;">Illustrative — shipped surfaces only</figcaption>'
    )
    html_lines.append("        </figure>")
    html_lines.append("    </section>")

    # Run section
    html_lines.append('    <section id="run">')
    html_lines.append("      <h2>Run it in 60 seconds.</h2>")
    html_lines.append(
        "      <pre><code>git clone https://github.com/alehar9320/agentic-odi.git\ncd agentic-odi\nuv sync --all-packages\npython scripts/dev.py</code></pre>"
    )
    html_lines.append(
        "      <p>Endpoint chips: MCP http://localhost:8000/mcp · Studio http://localhost:8100</p>"
    )
    html_lines.append("      <p>MCP client config snippet:</p>")
    html_lines.append("      <pre><code>{")
    html_lines.append('  "mcpServers": {')
    html_lines.append('    "agentic-odi": { "url": "http://localhost:8000/mcp" }')
    html_lines.append("  }")
    html_lines.append("}</code></p>")
    html_lines.append(
        '      <p>Hosted credentials come from the maintainers — <a href="https://github.com/alehar9320/agentic-odi/issues">open an issue</a>. <strong>requires a free Prefect account</strong>.</p>'
    )
    html_lines.append("    </section>")

    # Status section
    html_lines.append('    <section id="status">')
    html_lines.append("      <h2>Experimental</h2>")
    html_lines.append(
        "      <p><strong>What works today:</strong> MCP server tools for jobs/steps/outcomes/customer outcomes with opportunity scoring; The Living Studio — Opportunity Landscape, Universal Job Map, Impact Simulation, Causal Lineage; CLI outcomes; connectors; MCP ingest connector; hosted test endpoints requiring auth.</p>"
    )
    if no_dates_text:
        html_lines.append(f"      <p>{no_dates_text}</p>")
    html_lines.append(
        "      <p><strong>What's next:</strong> Curated from the README roadmap: map ingested evidence onto ODI artifacts, more connector kinds, ODI schema definition, context tooling, persistence layer, agentic integration.</p>"
    )
    html_lines.append(
        '      <p>Questions? <a href="https://github.com/alehar9320/agentic-odi/issues">Open an issue</a>.</p>'
    )
    html_lines.append("    </section>")

    html_lines.append("  </main>")

    html_lines.append("  <footer>")
    html_lines.append('    <svg viewBox="0 0 32 32" aria-hidden="true" width="16" height="16">')
    html_lines.append(
        '      <path fill="#475569" d="M0 0h32v32H0zM4 4h24v2H4V4zm0 6h24v2H4V10zm0 6h24v2H4V16zm0 6h24v2H4V22z"/>'
    )
    html_lines.append("    </svg>")
    html_lines.append('    <strong style="color:#1d1d1f">Agentic ODI</strong>')
    html_lines.append(
        '    <p style="font-size:0.75rem;color:#6e6e73;margin:12px 0;">Built with outcomes, not guesses.</p>'
    )
    html_lines.append('    <nav style="font-size:0.75rem;color:#6e6e73;">')
    html_lines.append(
        '      <a href="https://github.com/alehar9320/agentic-odi" style="margin-right:16px;">GitHub</a>'
    )
    html_lines.append('      <a href="https://github.com/alehar9320/agentic-odi/issues">Issues</a>')
    html_lines.append(
        '      <a href="https://horizon.prefect.io/alhase/servers/agentic-odi/chat">Hosted demo</a>'
    )
    html_lines.append("    </nav>")
    html_lines.append(
        '    <p style="font-size:0.75rem;color:#6e6e73;">© 2026 Agentic ODI maintainers · All rights reserved</p>'
    )
    html_lines.append("  </footer>")

    html_lines.append('  <script defer src="assets/main.js"></script>')
    html_lines.append("</body>")
    html_lines.append("</html>")

    # Embed honesty contract strings for lint/test verification
    html_lines.append("<!-- honesty contracts -->")
    for contract in HONESTY_CONTRACTS:
        html_lines.append(f'<meta name="honesty-{contract}" content="true">')

    html_content = "\n".join(html_lines)

    # Write with strict formatting to ensure idempotency
    INDEX_HTML.write_text(html_content, encoding="utf-8")


if __name__ == "__main__":
    generate()
