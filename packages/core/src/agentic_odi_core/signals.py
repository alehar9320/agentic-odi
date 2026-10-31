"""The "know" emission pass: record the facts Pillar 4 can prove.

Signals live in one inbox, recorded by writes (see ``ODIService.record_signal``)
and never re-derived on read, so the feed can never disagree with the store it
describes and an empty store yields an empty feed rather than demo rows.

The write-time kinds (``score_moved``, ``decision_superseded``) are recorded by
the service at the moment of the write. This module records the two kinds no
write can see — a bet coming due, and a stage with no outcomes — reading the
store and recording only what it can prove. Every emission carries a
deterministic ``discriminator``, so the inbox's fingerprint dedupe makes a
second pass a no-op: running it twice writes once.
"""

from __future__ import annotations

from datetime import datetime, timezone

from agentic_odi_core.models import (
    JOB_STAGE_ORDER,
    BetStatus,
    NotificationRule,
    Signal,
    SignalKind,
)

#: A score move below this magnitude is a wobble, not news. It matches the
#: approved default in E6.1 ("score movement off below ±0.5").
DEFAULT_SCORE_MOVE_THRESHOLD = 0.5


def default_rules() -> dict[SignalKind, NotificationRule]:
    """The documented default interruption policy.

    Bet-due and superseded decisions interrupt; score movement interrupts only
    past ±0.5; coverage gaps are shown in the feed but never interrupt.
    """
    return {
        SignalKind.BET_DUE: NotificationRule(kind=SignalKind.BET_DUE, enabled=True),
        SignalKind.SCORE_MOVED: NotificationRule(
            kind=SignalKind.SCORE_MOVED,
            enabled=True,
            threshold=DEFAULT_SCORE_MOVE_THRESHOLD,
        ),
        SignalKind.DECISION_SUPERSEDED: NotificationRule(
            kind=SignalKind.DECISION_SUPERSEDED, enabled=True
        ),
        SignalKind.COVERAGE_GAP: NotificationRule(kind=SignalKind.COVERAGE_GAP, enabled=False),
    }


def should_notify(signal: Signal, rules: dict[SignalKind, NotificationRule] | None = None) -> bool:
    """Whether a signal is allowed to interrupt, under the shared policy.

    Pure: it reads no clock and mutates nothing. A score move must clear the
    rule's threshold; the other kinds interrupt whenever they are enabled. A
    kind with no rule of its own never interrupts — it stays feed-only, so an
    unruled kind is an explicit "no" rather than an error.
    """
    policy = rules if rules is not None else default_rules()
    rule = policy.get(signal.kind)
    if rule is None:
        return False
    if not rule.enabled:
        return False
    if signal.kind is SignalKind.SCORE_MOVED:
        return signal.magnitude is not None and abs(signal.magnitude) >= rule.threshold
    return True


def emit_know_signals(
    service, *, job_id: str | None = None, now: datetime | None = None
) -> list[Signal]:
    """Record every "know" signal the store can prove, and return what is current.

    ``service`` is an :class:`~agentic_odi_core.services.ODIService`. The pass is
    idempotent: each emission's fingerprint is derived from the subject and the
    fact, so a second run records nothing new. It returns the signals it saw as
    current, including ones a previous run had already recorded.
    """
    when = now or datetime.now(timezone.utc)
    recorded: list[Signal] = []

    for bet in service.repo.list_bets(job_id):
        if bet.status in (BetStatus.PLANNED, BetStatus.RUNNING) and bet.measure_by <= when.date():
            recorded.append(
                service.record_signal(
                    SignalKind.BET_DUE,
                    f"Bet due: {bet.hypothesis}"[:120],
                    subject_kind="bet",
                    subject_id=bet.id,
                    severity="notice",
                    detail=f"Measure by {bet.measure_by.isoformat()}",
                    discriminator=bet.measure_by.isoformat(),
                )
            )

    for job in _scoped_jobs(service.repo, job_id):
        covered = _covered_stages(service.repo, job.id)
        for stage in JOB_STAGE_ORDER:
            if stage in covered:
                continue
            recorded.append(
                service.record_signal(
                    SignalKind.COVERAGE_GAP,
                    f"No outcomes captured in stage '{stage.value}'",
                    subject_kind="job_stage",
                    subject_id=f"{job.id}:{stage.value}",
                    severity="info",
                    detail=f"Job {job.name} has an empty stage",
                    discriminator=job.id,
                )
            )

    return recorded


def _scoped_jobs(repo, job_id: str | None) -> list:
    if job_id is not None:
        job = repo.get_job(job_id)
        return [job] if job is not None else []
    return repo.list_jobs()


def _covered_stages(repo, job_id: str) -> set:
    """Stages that have at least one outcome assigned through a step."""
    by_step: dict[str, int] = {}
    for outcome in repo.get_outcomes(job_id):
        if outcome.step_id:
            by_step[outcome.step_id] = by_step.get(outcome.step_id, 0) + 1
    covered = set()
    for step in repo.get_steps_for_job(job_id):
        if step.stage is not None and by_step.get(step.id):
            covered.add(step.stage)
    return covered


__all__ = [
    "DEFAULT_SCORE_MOVE_THRESHOLD",
    "default_rules",
    "emit_know_signals",
    "should_notify",
]
