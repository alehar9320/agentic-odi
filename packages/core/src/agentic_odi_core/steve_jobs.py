"""Steve Jobs Pass experience and rule-based fallback generator (Tier 0).

Delivers clear, elegant, human-centric responses focused on customer intent,
causality, and eliminating backlog friction.

Tier 0 never fabricates numbers, scores, quotes, or customer names. When the
user asks for an opportunity score, it points at ``compute_opportunity``
instead of computing one itself.
"""

from __future__ import annotations

from typing import Any


def generate_steve_jobs_response(
    user_input: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Generate an honest, zero-latency response (Tier 0 deterministic tier).

    Never fabricates customer data, scores, or quotes. Lists things the person
    can actually do — the tool names and surfaces — and points at
    ``compute_opportunity`` for scoring rather than inventing a number.
    """
    lowered = user_input.lower().strip()
    ctx = ""
    if context:
        parts = []
        if context.get("product_name"):
            parts.append(f"**{context['product_name']}**")
        if context.get("job_statement"):
            parts.append(context["job_statement"])
        if parts:
            ctx = "\n\n**Working context:** " + " — ".join(parts)

    if any(
        k in lowered for k in ["guideline", "framework", "stage", "process", "how does this work"]
    ):
        return (
            "### ODI, stage by stage\n\n"
            "1. **Define the job** — the functional progress a person is trying to make.\n"
            "2. **Capture desired outcomes** — `[direction] + [unit of measure] + [object of control] + [context]`.\n"
            "3. **Score the opportunity** — `importance + max(importance - satisfaction, 0)`; above 10 is underserved.\n"
            "4. **Map the job** — Define, Locate, Prepare, Confirm, Execute, Monitor, Modify, Conclude.\n\n"
            "Use `/capture` to record an outcome, `/jobmap` to walk the phases, "
            "and `/landscape` to see what is underserved." + ctx
        )

    if any(k in lowered for k in ["simulate", "bet", "impact", "friction", "time-to-value"]):
        return (
            "### Simulate the bet by hand\n\n"
            "Open `/impact` and pick the outcome you want to test. The simulation "
            "shows before/after friction; it no longer invents a result when no "
            "model is connected." + ctx
        )

    if any(
        k in lowered for k in ["evidence", "call", "quote", "transcript", "research", "lineage"]
    ):
        return (
            "### Evidence needs a source\n\n"
            "No connector is wired up, so there is no live transcript to quote. "
            "Capture the signal you already have in `/capture` — the evidence field "
            "is stored with the outcome." + ctx
        )

    if any(k in lowered for k in ["score", "opportunity", "calculate"]):
        return (
            "### Opportunity score\n\n"
            "I can't compute a score without a model connected. Use "
            "`compute_opportunity(importance, satisfaction)` — "
            "`importance + max(importance - satisfaction, 0)` — above 10 is "
            "underserved. Type the two numbers and I'll point you at the right "
            "surface." + ctx
        )

    return (
        f'I received your intent: **"{user_input.strip()}"**.'
        + ctx
        + "\n\nNo model is reachable right now, so I'm running in deterministic "
        "mode. I can't reason about that with a model, but the studio still "
        "works by hand:\n\n"
        "- `/start` — set or correct your context\n"
        "- `/capture` — record an outcome with importance and satisfaction\n"
        "- `/jobmap` — add or edit the steps of the job\n"
        "- `/landscape` — review what is underserved\n\n"
        "Type `/help` for every command, or point Settings at a local model to "
        "bring the assistant back."
    )


# Deprecated: Tier 0 must not compute or present opportunity scores.
# Kept for backward compatibility only; callers should use compute_opportunity
# from agentic_odi_core.models instead.
def format_opportunity_score_insight(
    importance: float, satisfaction: float, statement: str | None = None
) -> str:
    """Format an opportunity score calculation (deprecated in Tier 0)."""
    gap = max(importance - satisfaction, 0.0)
    score = importance + gap

    if score > 10.0:
        verdict = "underserved"
    elif score == 10.0:
        verdict = "appropriately served"
    else:
        verdict = "overserved"

    stmt_header = (
        f'Outcome: "{statement}"\n\n' if statement else "Opportunity Score Calculation\n\n"
    )
    return (
        f"{stmt_header}"
        f"Importance: {importance:.1f}/10\n"
        f"Satisfaction: {satisfaction:.1f}/10\n"
        f"Formula: Importance + max(Importance - Satisfaction, 0)\n"
        f"Score: {score:.2f} → {verdict}"
    )
