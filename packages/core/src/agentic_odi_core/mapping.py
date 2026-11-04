"""Evidence-to-outcome proposal engine.

Turns ingested evidence records into scored, approvable desired-outcome
proposals. The default strategy is deterministic and offline — no LLM, no
network — so proposals are inspectable and reproducible.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field

from agentic_odi_core.evaluation import evaluate_outcome_statement
from agentic_odi_core.models import Direction, Evidence, Job, Step


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class OutcomeProposal(BaseModel):
    """A candidate desired outcome mined from an evidence record.

    Nothing is written to the ODI store until a human approves the proposal.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_id: str
    job_id: str | None = None
    step_id: str | None = None
    statement: str
    direction: Direction
    unit_of_measure: str | None = None
    object_of_control: str | None = None
    contextual_clarifier: str | None = None
    importance: float | None = None
    satisfaction: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    quote: str | None = None
    source_name: str
    status: ProposalStatus = ProposalStatus.PROPOSED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Complaint patterns that indicate a customer problem worth capturing as an
# outcome statement.
_COMPLAINT_PATTERNS = (
    r"\bhard\b",
    r"\bslow\b",
    r"\btakes\b",
    r"\bconfusing\b",
    r"\bcannot\b",
    r"\bcan.t\b",
    r"\bkeeps\b",
    r"\bwaiting\b",
    r"\bmanually\b",
    r"\btedious\b",
    r"\bfrustrating\b",
    r"\bbroken\b",
    r"\berror\b",
    r"\bfail\b",
    r"\bstuck\b",
)


class ProposalStrategy(Protocol):
    """Pluggable strategy for proposing outcomes from evidence."""

    def propose(
        self, evidence: Evidence, jobs: Sequence[Job], steps: Sequence[Step]
    ) -> OutcomeProposal | None:
        """Propose an outcome from evidence, or None if no candidate found."""


class HeuristicProposalStrategy:
    """Deterministic, offline proposal strategy.

    Routes evidence to a job and step by term overlap, extracts a candidate
    outcome statement from complaint patterns, and suggests importance /
    satisfaction from signals present in the record.
    """

    def __init__(self, job_route_threshold: float = 0.1) -> None:
        self.job_route_threshold = job_route_threshold

    def propose(
        self, evidence: Evidence, jobs: Sequence[Job], steps: Sequence[Step]
    ) -> OutcomeProposal | None:
        job_id, job = self._route_to_job(evidence, jobs)
        step_id = self._route_to_step(evidence, steps, job)
        proposal = self._extract_outcome(evidence, job_id, step_id)
        return proposal

    def _route_to_job(
        self, evidence: Evidence, jobs: Sequence[Job]
    ) -> tuple[str | None, Job | None]:
        if not jobs:
            return None, None

        # A record that already names its job is routed there; term overlap is
        # only the fallback for unlinked evidence.
        if evidence.job_id is not None:
            for job in jobs:
                if job.id == evidence.job_id:
                    return job.id, job

        evidence_terms = self._terms(evidence.name + " " + evidence.content)
        if not evidence_terms:
            return None, None

        best_job: Job | None = None
        best_score = 0.0

        for job in jobs:
            job_terms = self._terms(job.name + " " + (job.description or ""))
            if not job_terms:
                continue
            overlap = len(evidence_terms & job_terms) / len(evidence_terms | job_terms)
            score = overlap
            if score > best_score:
                best_score = score
                best_job = job

        if best_job is None or best_score < self.job_route_threshold:
            return None, None
        return best_job.id, best_job

    def _route_to_step(
        self, evidence: Evidence, steps: Sequence[Step], job: Job | None
    ) -> str | None:
        if job is None or not steps:
            return None

        job_steps = [s for s in steps if s.job_id == job.id]
        if not job_steps:
            return None

        evidence_terms = self._terms(evidence.name + " " + evidence.content)
        if not evidence_terms:
            return None

        best_step: Step | None = None
        best_score = 0.0

        for step in job_steps:
            step_terms = self._terms(step.name + " " + (step.stage.value if step.stage else ""))
            if not step_terms:
                continue
            overlap = len(evidence_terms & step_terms) / len(evidence_terms | step_terms)
            score = overlap
            if score > best_score:
                best_score = score
                best_step = step

        if best_step is None or best_score < self.job_route_threshold:
            return None
        return best_step.id

    def _extract_outcome(
        self, evidence: Evidence, job_id: str | None, step_id: str | None
    ) -> OutcomeProposal | None:
        text = evidence.content
        sentences = re.split(r"[.!?]+", text)
        complaint_sentence: str | None = None

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            lowered = sentence.lower()
            for pattern in _COMPLAINT_PATTERNS:
                if re.search(pattern, lowered):
                    complaint_sentence = sentence
                    break
            if complaint_sentence:
                break

        if complaint_sentence is None:
            return None

        # Compose the ODI 4-part format from the complaint sentence.
        direction = self._infer_direction(complaint_sentence)
        unit_of_measure = self._find_unit_of_measure(complaint_sentence)
        object_of_control = self._find_object_of_control(complaint_sentence)
        contextual_clarifier = self._find_context(complaint_sentence)

        statement = self._compose_statement(
            direction, unit_of_measure, object_of_control, contextual_clarifier
        )
        if statement is None:
            return None

        # Validate the statement against the shared ODI validator.
        verdict = evaluate_outcome_statement(statement)
        if not verdict["valid"]:
            return None

        importance, satisfaction, confidence = self._score_signals(evidence)
        rationale = (
            f"Evidence '{evidence.name}' routed to job {job_id or 'unmatched'} "
            f"(step {step_id or 'unmatched'}); complaint phrase: "
            f"{complaint_sentence[:80]}{'…' if len(complaint_sentence) > 80 else ''}"
        )

        return OutcomeProposal(
            evidence_id=evidence.id,
            job_id=job_id,
            step_id=step_id,
            statement=statement,
            direction=direction,
            unit_of_measure=unit_of_measure,
            object_of_control=object_of_control,
            contextual_clarifier=contextual_clarifier,
            importance=importance,
            satisfaction=satisfaction,
            confidence=confidence,
            rationale=rationale,
            quote=complaint_sentence,
            source_name=evidence.source_name,
        )

    @staticmethod
    def _terms(text: str) -> set[str]:
        return {t for t in re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())}

    @staticmethod
    def _infer_direction(text: str) -> Direction:
        lowered = text.lower()
        if "maximize" in lowered or any(w in lowered for w in ("increase", "boost", "grow")):
            return Direction.MAXIMIZE
        return Direction.MINIMIZE

    @staticmethod
    def _find_unit_of_measure(text: str) -> str | None:
        units = (
            "time",
            "hours",
            "minutes",
            "seconds",
            "days",
            "weeks",
            "months",
            "years",
            "cost",
            "number",
            "frequency",
            "rate",
            "percentage",
            "steps",
            "attempts",
            "likelihood",
            "duration",
            "errors",
        )
        # Time-implying words map to the "time" unit.
        time_words = ("long", "slow", "quick", "fast", "rapid", "speed", "duration")
        lowered = text.lower()
        for unit in units:
            if re.search(rf"\b{re.escape(unit)}\b", lowered):
                return unit
        for word in time_words:
            if re.search(rf"\b{re.escape(word)}\b", lowered):
                return "time"
        if re.search(r"\d", text):
            return "number"
        return None

    @staticmethod
    def _find_object_of_control(text: str) -> str | None:
        """Extract the object of control from the complaint sentence.

        Looks first for the noun phrase after a common action verb
        (rotate, fix, resolve, complete, etc.), then falls back to
        the noun phrase after "the".
        """
        # Pattern 1: <action verb> <object>
        action_verbs = (
            "rotate",
            "fix",
            "resolve",
            "complete",
            "find",
            "locate",
            "access",
            "retrieve",
            "update",
            "delete",
            "create",
            "deploy",
            "copy",
            "paste",
            "enter",
            "submit",
            "approve",
            "review",
        )
        for verb in action_verbs:
            match = re.search(
                rf"\b{re.escape(verb)}\s+([a-zA-Z][a-zA-Z\s]{{2,40}}?)"
                rf"(?:\s+when|\s+while|\s+before|\s+after|\s+during|\s+if|\s+as|\.|$)",
                text,
            )
            if match:
                obj = match.group(1).strip()
                obj = re.sub(r"^(the|a|an)\s+", "", obj)
                if obj:
                    return obj

        # Pattern 2: "the <object>"
        match = re.search(
            r"\bthe\s+([a-zA-Z][a-zA-Z\s]{2,40}?)(?:\s+when|\s+while|\s+before|\s+after|\s+during|\s+if|\s+as|\.|$)",
            text,
        )
        if match:
            obj = match.group(1).strip()
            if obj:
                return obj

        return None

    @staticmethod
    def _find_context(text: str) -> str | None:
        markers = (" when ", " while ", " before ", " after ", " during ", " if ", " as ")
        lowered = " " + text.lower() + " "
        for marker in markers:
            if marker in lowered:
                # Return the marker plus whatever follows until end of sentence
                start = lowered.index(marker)
                end = len(text)
                for term in (".", "!", "?"):
                    idx = text.find(term, start)
                    if idx != -1 and idx < end:
                        end = idx
                phrase = text[start:end].strip()
                return phrase
        # Marker at end of sentence followed by period
        for marker in ("when", "while", "before", "after", "during", "if", "as"):
            match = re.search(rf"\b{marker}\s+([^.!?]+)", text.lower())
            if match:
                return f"{marker} {match.group(1).strip()}"
        return None

    @classmethod
    def _compose_statement(
        cls,
        direction: Direction,
        unit_of_measure: str | None,
        object_of_control: str | None,
        contextual_clarifier: str | None,
    ) -> str | None:
        """Compose an ODI 4-part outcome statement."""
        if not object_of_control:
            return None

        parts: list[str] = [direction.value]
        if unit_of_measure:
            parts.append(f"the {unit_of_measure}")
        parts.append("to")
        parts.append(object_of_control)
        if contextual_clarifier:
            parts.append(contextual_clarifier)

        statement = " ".join(parts)
        statement = statement[0].upper() + statement[1:]
        if not statement.endswith("."):
            statement += "."
        return statement

    @classmethod
    def _score_signals(cls, evidence: Evidence) -> tuple[float | None, float | None, float]:
        """Suggest importance and satisfaction from record signals.

        These are suggestions with stated confidence, never measurements.
        """
        lowered = evidence.content.lower()

        # Frequency: how many times the complaint pattern appears
        complaint_count = sum(1 for pattern in _COMPLAINT_PATTERNS if re.search(pattern, lowered))
        severity = any(w in lowered for w in ("cannot", "broken", "error", "fail", "stuck"))
        workaround = any(w in lowered for w in ("workaround", "manually", "copy-paste", "retry"))
        speakers = len(set(re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", evidence.content)))

        # Importance: higher if severe, frequent, or many speakers
        importance = 5.0
        if severity:
            importance += 2.0
        if complaint_count > 1:
            importance += 1.0
        if speakers > 1:
            importance += 1.0
        importance = min(10.0, max(1.0, importance))

        # Satisfaction: lower if severe or workaround needed
        satisfaction = 5.0
        if severity:
            satisfaction -= 2.0
        if workaround:
            satisfaction -= 1.0
        satisfaction = min(10.0, max(1.0, satisfaction))

        # Confidence: higher with more signal
        confidence = 0.4
        if complaint_count > 0:
            confidence += 0.2
        if severity:
            confidence += 0.2
        if speakers > 1:
            confidence += 0.1
        confidence = min(0.95, max(0.1, confidence))

        return importance, satisfaction, confidence


__all__ = [
    "OutcomeProposal",
    "ProposalStatus",
    "ProposalStrategy",
    "HeuristicProposalStrategy",
]
