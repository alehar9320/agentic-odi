"""Steve Jobs Pass experience and rule-based fallback generator.

Delivers clear, elegant, human-centric responses focused on customer intent,
causality, and eliminating backlog friction.
"""

from __future__ import annotations

import re
from typing import Any


def format_opportunity_score_insight(
    importance: float, satisfaction: float, statement: str | None = None
) -> str:
    """Format an opportunity score calculation with Steve Jobs clarity."""
    gap = max(importance - satisfaction, 0.0)
    score = importance + gap

    if score > 10.0:
        verdict = "**Breakthrough Opportunity** (Underserved Need)"
        action = "Focus product strategy here. Customers are dissatisfied relative to importance."
    elif score == 10.0:
        verdict = "**Appropriately Served**"
        action = "Maintain current quality. Do not over-engineer."
    else:
        verdict = "**Overserved Target**"
        action = "Potential candidate for disruptive, low-cost alternatives."

    stmt_header = (
        f'### Outcome Analysis: *"{statement}"*\n\n'
        if statement
        else "### Opportunity Score Calculation\n\n"
    )

    return (
        f"{stmt_header}"
        f"- **Importance**: {importance:.1f}/10\n"
        f"- **Satisfaction**: {satisfaction:.1f}/10\n"
        f"- **Formula**: `Importance + max(Importance - Satisfaction, 0)`\n"
        f"- **Opportunity Score**: **{score:.2f}** → {verdict}\n\n"
        f"**Strategic Imperative**: {action}"
    )


def generate_steve_jobs_response(user_input: str, context: dict[str, Any] | None = None) -> str:
    """Generate a zero-latency, highly polished response passing the Steve Jobs Pass."""
    lowered = user_input.lower().strip()

    # Calculate Opportunity score directly if numbers are detected
    numbers = re.findall(r"\b([0-9]|10)(?:\.0)?\b", lowered)
    if ("score" in lowered or "opportunity" in lowered or "calculate" in lowered) and len(
        numbers
    ) >= 2:
        try:
            imp, sat = float(numbers[0]), float(numbers[1])
            return format_opportunity_score_insight(imp, sat)
        except ValueError:
            pass

    if any(
        k in lowered for k in ["guideline", "framework", "stage", "process", "how does this work"]
    ):
        return (
            "### 📖 Outcome-Driven Innovation (ODI) Process Guidelines\n\n"
            "Products change. Features rot. **Human jobs remain constant.** Here is how we build what people actually need:\n\n"
            "1. **Stage 1: Define Intent (Job-to-be-Done)**\n"
            "   - Stop writing Jira cards. Identify the core functional human goal.\n"
            "2. **Stage 2: Capture Desired Outcomes**\n"
            "   - Measure success with standard syntax:\n"
            "     `[Direction] + [Unit of Measure] + [Object of Control] + [Contextual Clarifier]`\n"
            "3. **Stage 3: Compute Opportunity Scores**\n"
            "   - `Opportunity Score = Importance + max(Importance - Satisfaction, 0)`\n"
            "   - Anything **> 10.0** is an underserved market opportunity waiting for design leadership.\n"
            "4. **Stage 4: Universal Job Map**\n"
            "   - Chronological flow: Define ➔ Locate ➔ Prepare ➔ Confirm ➔ Execute ➔ Monitor ➔ Modify ➔ Conclude.\n\n"
            "*Every line of code you write should directly elevate customer satisfaction or collapse execution time.*"
        )

    if any(k in lowered for k in ["simulate", "bet", "impact", "friction", "time-to-value"]):
        return (
            "### ⚡ WYSIWYG Impact Simulation Result\n\n"
            "- **Target Outcome**: O-1 (*Minimize time taken to propagate secrets*)\n"
            "- **Proposed Bet**: Automated Secret Sync Daemon\n"
            "- **Before**: 45 minutes of manual copy-paste across 400 developer pipelines.\n"
            "- **After**: Under 30 seconds ambient zero-touch sync.\n"
            "- **Time-to-Value Shift**: **-90% friction reduction**.\n"
            "- **Human Impact**: 3,000 hours of developer agony eliminated every month. Build it."
        )

    if any(
        k in lowered for k in ["evidence", "call", "quote", "transcript", "research", "lineage"]
    ):
        return (
            "### 🔍 Causal Lineage: Real-Time Evidence\n\n"
            "- **Signal Source**: Gong Call #104 (Enterprise Team Alpha)\n"
            "- **Customer Voice**: *'We lost two hours on deploy day because someone missed a database config key.'*\n"
            "- **Telemetry**: 400 microservices impacted weekly; 14% failed build rate attributed to config drift."
        )

    return (
        f'I received your intent: **"{user_input.strip()}"**.\n\n'
        "In The Living Studio, every idea is evaluated against human outcomes rather than story points. "
        "Notice how our highest opportunity outcome (`O-1: Minimize propagation time`) has an **Opportunity Score of 15.3**, "
        "signaling severe market underservice. Tap **'Simulate Impact'** on the canvas or type `Simulate Auto-Sync Bet` to test causality."
    )
