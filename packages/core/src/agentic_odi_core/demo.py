"""A labelled demo workspace you can load on purpose.

One command fills a store with a realistic, deterministic corpus so a newcomer
sees a filled canvas without doing the research first. Every row carries
``origin="demo"`` and a deterministic id, so the sample can never be mistaken
for the user's own data and loading twice is a no-op.

The fixture is *typed*: it builds :class:`Job`, :class:`Step`, :class:`Outcome`
and :class:`Evidence` models, not dicts. A dict fixture is how fabricated fields
get in, and every write goes through the same validators the user's own writes
do.

Segments, decisions and bets are deliberately absent: they arrived after this
fixture was scoped, and a demo that claims an entity the loop cannot yet hold
would be exactly the fabrication this loader exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from agentic_odi_core.evaluation import require_outcome_statement
from agentic_odi_core.models import (
    JOB_STAGE_ORDER,
    Evidence,
    Job,
    Outcome,
    Step,
    compute_opportunity_score,
)
from agentic_odi_core.repository import Repository

if TYPE_CHECKING:
    from agentic_odi_core.spine import DemoWorkspace

DEMO_JOB_ID = "demo-job-1"

#: (verb, object, context) triples. Each becomes a valid ODI statement of the
#: form "Minimize the time it takes to <verb> <object> when <context>." The
#: statements are generated rather than pasted so forty of them cannot drift
#: out of the ODI format one edit at a time.
_DEMO_OUTCOME_SEEDS: tuple[tuple[str, str, str], ...] = (
    ("rotate", "expired credentials", "a deployment starts"),
    ("locate", "the correct environment variables", "a new service is added"),
    ("confirm", "a secret has the right scope", "a pipeline is promoted"),
    ("propagate", "a key change to every cluster", "a rotation is scheduled"),
    ("detect", "a leaked secret in build logs", "a merge request is opened"),
    ("recover", "from a broken secret reference", "a deploy fails"),
    ("audit", "which service owns a secret", "an incident is declared"),
    ("onboard", "a new engineer to the vault", "they join the team"),
    ("prepare", "the secrets payload for staging", "a release is cut"),
    ("verify", "permissions before a deploy", "a change window opens"),
    ("synchronise", "staging and production keys", "an environment is cloned"),
    ("revoke", "access for a departing engineer", "their last day arrives"),
    ("trace", "where a credential was last used", "a compromise is suspected"),
    ("roll", "a credential without downtime", "a rotation deadline passes"),
    ("test", "a rotation against the CI pipeline", "a policy changes"),
    ("document", "which key belongs to which service", "a handover happens"),
    ("review", "the secret inventory", "a compliance audit starts"),
    ("restore", "a previous secret version", "a bad value is deployed"),
    ("monitor", "secret access across services", "a suspicious read occurs"),
    ("limit", "the blast radius of a leaked key", "a breach is detected"),
    ("automate", "the copy step between environments", "a config drifts"),
    ("validate", "an environment before promotion", "a release candidate is built"),
    ("encrypt", "secrets at rest in the cluster", "a node is provisioned"),
    ("share", "a secret with a teammate", "pairing on an incident"),
    ("compare", "local and remote configuration", "a developer debugs a build"),
    ("inventory", "every secret a service depends on", "a dependency is added"),
    ("rotate", "a database password", "a scheduled window arrives"),
    ("map", "a secret to the team that owns it", "an ownership review runs"),
    ("clean", "stale credentials", "a quarterly review is held"),
    ("stage", "a new secret safely", "a developer joins a project"),
    ("promote", "a verified secret", "a release is approved"),
    ("align", "naming across environments", "a new team adopts the vault"),
    ("trace", "a failed authentication", "a support ticket is filed"),
    ("provision", "secrets for a fresh cluster", "an environment is created"),
    ("escalate", "a blocked deployment", "a secret is missing"),
    ("predict", "which keys will expire soon", "a maintenance window is planned"),
    ("measure", "how long a rotation takes", "a process review happens"),
    ("reduce", "the number of manual secret steps", "a release is prepared"),
    ("centralise", "secret ownership records", "a reorganisation occurs"),
    ("surface", "a risky permission early", "a policy is authored"),
)

_DEMO_EVIDENCE_SEEDS: tuple[tuple[str, str, str], ...] = (
    (
        "Interview",
        "Platform engineer #12",
        "Manual copy-paste between Vault and CI broke staging twice last quarter.",
    ),
    (
        "Interview",
        "Security lead #4",
        "Rotation is scheduled but nobody owns verifying it actually ran.",
    ),
    (
        "Support ticket",
        "Ticket 8841",
        "Deploy failed because a secret scope was too narrow for the new service.",
    ),
    (
        "Support ticket",
        "Ticket 9012",
        "An expired credential took down the payments worker for forty minutes.",
    ),
    ("Audit", "SOC2 evidence", "Three services shared a single credential with no owner recorded."),
    (
        "Audit",
        "Q3 access review",
        "Nine departed engineers still had vault access after offboarding.",
    ),
    ("Telemetry", "CI metrics", "Average secret rotation takes 45 minutes of manual coordination."),
    ("Telemetry", "Access logs", "A staging key was read from a production pod eleven times."),
    ("Interview", "SRE #7", "We cannot tell which service owns a key during an incident."),
    (
        "Survey",
        "Onboarding poll",
        "New engineers take most of a day to get their first deploy through.",
    ),
    (
        "Incident",
        "Postmortem 2026-08",
        "A leaked key in a build log required a full rotation of twelve services.",
    ),
    (
        "Interview",
        "Compliance officer",
        "Auditors ask for secret ownership and we produce a spreadsheet.",
    ),
)


@dataclass(frozen=True)
class DemoLoadResult:
    """The exact counts a demo load produced, asserted per entity."""

    job_id: str
    jobs: int
    steps: int
    outcomes: int
    evidence: int


def demo_job() -> Job:
    return Job(
        id=DEMO_JOB_ID,
        name="Sync environment secrets across microservices",
        description=(
            "Backend developers keeping deployment secrets consistent across "
            "staging and production."
        ),
        origin="demo",
    )


def demo_steps() -> list[Step]:
    names = (
        "Define required environment variables",
        "Locate credentials in the vault",
        "Prepare the secrets payload",
        "Confirm access permissions and scopes",
        "Execute the secret update",
        "Monitor the pipeline for missing config",
        "Modify mismatched keys after a failed deploy",
        "Conclude the deployment confirmation",
    )
    steps: list[Step] = []
    for index, (stage, name) in enumerate(zip(JOB_STAGE_ORDER, names, strict=True), start=1):
        steps.append(
            Step(
                id=f"demo-step-{index}",
                job_id=DEMO_JOB_ID,
                name=name,
                order=index,
                stage=stage,
                stage_index=index,
                origin="demo",
            )
        )
    return steps


def demo_outcomes() -> list[Outcome]:
    """Forty scored outcomes, each a valid ODI statement.

    Scores are deterministic: importance and satisfaction cycle through fixed
    values so the landscape has a stable shape and a test can recompute every
    opportunity score independently of the loader.
    """
    outcomes: list[Outcome] = []
    for index, (verb, obj, context) in enumerate(_DEMO_OUTCOME_SEEDS):
        statement = f"Minimize the time it takes to {verb} {obj} when {context}."
        require_outcome_statement(statement)
        importance = float(6 + (index % 5))  # 6..10
        satisfaction = float(2 + (index % 7))  # 2..8
        step_index = (index % len(JOB_STAGE_ORDER)) + 1
        outcomes.append(
            Outcome(
                id=f"demo-outcome-{index + 1}",
                job_id=DEMO_JOB_ID,
                step_id=f"demo-step-{step_index}",
                statement=statement,
                importance=importance,
                satisfaction=satisfaction,
                opportunity_score=compute_opportunity_score(importance, satisfaction),
                origin="demo",
            )
        )
    return outcomes


def demo_evidence() -> list[Evidence]:
    evidence: list[Evidence] = []
    for index, (kind, name, content) in enumerate(_DEMO_EVIDENCE_SEEDS):
        evidence.append(
            Evidence(
                id=f"demo-evidence-{index + 1}",
                source_name=name,
                source_kind="manual",
                item_type="note",
                name=f"{kind}: {name}",
                content=content,
                job_id=DEMO_JOB_ID,
                origin="demo",
            )
        )
    return evidence


def load_demo(repo: Repository, *, name: str = "demo") -> DemoLoadResult:
    """Upsert the labelled demo corpus into ``repo``; a second load is a no-op.

    Writes through the repository by deterministic id, so loading twice leaves
    the counts unchanged and never touches the user's own rows. Statements were
    already validated when the fixture was built.
    """
    job = demo_job()
    repo.add_job(job)
    steps = demo_steps()
    for step in steps:
        repo.add_step(step)
    outcomes = demo_outcomes()
    for outcome in outcomes:
        repo.add_outcome(outcome)
    evidence = demo_evidence()
    for row in evidence:
        repo.add_evidence(row)
    return DemoLoadResult(
        job_id=job.id,
        jobs=1,
        steps=len(steps),
        outcomes=len(outcomes),
        evidence=len(evidence),
    )


class StoreDemoLoader:
    """The real ``demo`` seam: load the labelled sample workspace into the store.

    Implements the :class:`~agentic_odi_core.spine.DemoLoader` protocol so the
    capability inventory can report the demo seam as available.
    """

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def load(self, *, name: str = "demo") -> DemoWorkspace:
        from agentic_odi_core.spine import DemoWorkspace

        result = load_demo(self._repo, name=name)
        return DemoWorkspace(
            name=name,
            job_ids=(result.job_id,),
            labelled=True,
        )


__all__ = [
    "DEMO_JOB_ID",
    "DemoLoadResult",
    "StoreDemoLoader",
    "demo_evidence",
    "demo_job",
    "demo_outcomes",
    "demo_steps",
    "load_demo",
]
