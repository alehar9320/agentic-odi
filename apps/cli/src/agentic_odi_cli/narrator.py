"""The CLI's narrator: the one place ``odi brief --narrate`` reaches a model.

This adapter implements :class:`~agentic_odi_core.brief.Narrator`. It asks an
OpenAI-compatible model to draft the brief's argument as structured claims, then
hands the raw draft to :func:`~agentic_odi_core.brief.render_narrative`, which
keeps only the sentences whose numbers are in the brief and whose outcomes are
linked. This module never decides what is true; it only fetches a proposal.

Every failure — no provider configured, timeout, malformed output — raises
:class:`~agentic_odi_core.brief.NarratorError`, so the caller degrades to the
factual brief with a recorded reason instead of failing the export or printing
an unchecked sentence. There are no retries: a bounded wait, then honesty.
"""

from __future__ import annotations

import json
from typing import Any

from agentic_odi_core import (
    BriefInput,
    DraftedClaim,
    NarrativeDraft,
    NarratorError,
)

#: A person waiting for a terminal export should not wait long. The wait is
#: bounded here rather than in the core so the guarantee stays pure.
DEFAULT_TIMEOUT_SECONDS = 30.0

_SYSTEM_PROMPT = (
    "You draft the argument for a product decision brief. You are given the "
    "brief's own numbers. Write short sentences an executive reads first: what "
    "the evidence supports, what we should do, and the risks. Every sentence "
    "must be true of the numbers given. Never invent a number, a date, or a "
    "source. Reply with JSON only, shaped as "
    '{"supported": [{"claim": str, "outcome_ids": [str]}], '
    '"recommendation": [{"claim": str, "outcome_ids": [str]}], '
    '"risks": [{"claim": str, "outcome_ids": [str]}]}. '
    "Every supported and recommendation claim must link at least one outcome id "
    "from the brief."
)


def _brief_for_prompt(brief: BriefInput) -> str:
    """A compact, factual view of the brief for the prompt.

    Only supplied measurements appear; an unscored outcome is stated as such, so
    the model cannot read a zero that was never measured.
    """
    lines = [f"Job: {brief.job_name} (id {brief.job_id})"]
    if brief.decision_consideration:
        lines.append(f"Decision under consideration: {brief.decision_consideration}")
    lines.append(f"Evidence records: {brief.evidence_count}")
    lines.append("Outcomes:")
    for outcome in brief.outcomes:
        score = "not measured" if outcome.score is None else f"{outcome.score:g}"
        sample = "not measured" if outcome.n is None else str(outcome.n)
        lines.append(
            f"- id {outcome.outcome_id}: {outcome.statement} "
            f"(opportunity score {score}; sample {sample})"
        )
    if brief.holes:
        lines.append("Recorded holes: " + "; ".join(brief.holes))
    return "\n".join(lines)


def _claims(raw: Any) -> tuple[DraftedClaim, ...]:
    """Parse a section's claims defensively. Malformed input raises."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise NarratorError("narrator returned a section that is not a list")
    claims: list[DraftedClaim] = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("claim"), str):
            raise NarratorError("narrator returned a claim without a string 'claim'")
        links = item.get("outcome_ids") or []
        if not isinstance(links, list) or not all(isinstance(link, str) for link in links):
            raise NarratorError("narrator returned outcome_ids that are not strings")
        claims.append(DraftedClaim(item["claim"], tuple(links)))
    return tuple(claims)


def parse_draft(text: str) -> NarrativeDraft:
    """Turn a model's raw reply into a :class:`NarrativeDraft`.

    The reply may carry a fenced code block; the JSON inside is used. Anything
    that is not the expected shape raises :class:`NarratorError`, so a garbled
    reply becomes a recorded drop reason, never a printed sentence.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        stripped = stripped.rsplit("```", 1)[0]
    try:
        payload = json.loads(stripped)
    except (ValueError, TypeError) as error:
        raise NarratorError(f"narrator returned invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise NarratorError("narrator returned JSON that is not an object")
    return NarrativeDraft(
        supported=_claims(payload.get("supported")),
        recommendation=_claims(payload.get("recommendation")),
        risks=_claims(payload.get("risks")),
    )


class OpenAINarrator:
    """A :class:`Narrator` backed by an OpenAI-compatible chat completion."""

    def __init__(
        self, client: Any, model: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
    ) -> None:
        self._client = client
        self._model = model
        self._timeout = timeout

    @classmethod
    def from_env(cls, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> OpenAINarrator:
        """Build a narrator from the same settings ``odi chat`` uses.

        Imported lazily so ``--narrate`` is the only path that needs the OpenAI
        dependency and the profile file.
        """
        from openai import OpenAI

        from agentic_odi_cli.chat import ChatConfig

        config = ChatConfig.from_env()
        client = OpenAI(base_url=config.base_url, api_key=config.api_key, timeout=timeout)
        return cls(client, config.model, timeout=timeout)

    def draft(self, brief: BriefInput) -> NarrativeDraft:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _brief_for_prompt(brief)},
                ],
                timeout=self._timeout,
            )
        except Exception as error:  # noqa: BLE001 - any transport failure is a drop
            raise NarratorError(f"model unavailable: {error}") from error
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as error:
            raise NarratorError(f"model returned an unusable response: {error}") from error
        if not isinstance(content, str) or not content.strip():
            raise NarratorError("model returned an empty response")
        return parse_draft(content)
