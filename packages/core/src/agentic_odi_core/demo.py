"""The demo workspace: one complete ODI study, labeled and repeatable.

``odi demo load`` exists so someone can see a filled canvas before they have any
research of their own. That only works under two conditions, and both live here:
every row announces itself with ``origin="demo"``, and the rows are deterministic
enough that loading the study a second time is a no-op rather than a duplicate.

The study is one Job with a full eight-stage job map, forty desired outcomes
carrying importance and satisfaction, and twelve research records tied to the
outcome they bear on. Nothing here is real customer data; nothing here is
invented to fill a field the schema does not have.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentic_odi_core.models import (
    JOB_STAGE_ORDER,
    Evidence,
    EvidenceItemType,
    Job,
    JobStage,
    Outcome,
    Step,
    compute_opportunity_score,
)
from agentic_odi_core.repository import Repository
from agentic_odi_core.services import JobNotFoundError, ODIService

DEMO_JOB_ID = "JOB-402"
DEMO_JOB_NAME = "Sync Environment Secrets Across Microservices"
DEMO_JOB_DESCRIPTION = "Backend developers configuring microservice deployment pipelines across staging and production."

#: What the fixture contains, so a loader can promise it and a test can check it.
FIXTURE_COUNTS: dict[str, int] = {
    "jobs": 1,
    "steps": len(JOB_STAGE_ORDER),
    "outcomes": 40,
    "evidence": 12,
}

#: One step per Universal Job Map stage, in canonical order.
_STEP_NAMES: tuple[str, ...] = (
    "1. Define required environment variables",
    "2. Locate credentials in Vault / 1Password",
    "3. Prepare secrets payload for cluster",
    "4. Confirm access permissions & scopes",
    "5. Execute manual copy-paste into CI/CD secrets",
    "6. Monitor pipeline build for config missing errors",
    "7. Modify mismatched keys upon failed deploy",
    "8. Conclude deployment confirmation",
)

#: (statement, importance, satisfaction) per step, five outcomes to a stage.
#: Scores are the interview answers the study would have collected; the
#: opportunity score is derived, never stored as a third opinion.
_OUTCOME_SETS: tuple[tuple[JobStage, tuple[tuple[str, float, float], ...]], ...] = (
    (
        JobStage.DEFINE,
        (
            (
                "Minimize the time it takes to agree on which secrets a service needs "
                "when starting a pipeline",
                8.4,
                4.1,
            ),
            (
                "Minimize the number of secret requirements left unwritten when a service "
                "moves to another team",
                7.2,
                6.3,
            ),
            (
                "Minimize the time spent re-deriving secret criteria when an environment is "
                "cloned from another",
                6.5,
                5.0,
            ),
            (
                "Maximize the share of deployment goals that name a secret owner when those "
                "goals are written",
                7.8,
                3.6,
            ),
            (
                "Minimize the number of naming disputes over one secret when two teams meet "
                "for the first time",
                6.1,
                6.1,
            ),
        ),
    ),
    (
        JobStage.LOCATE,
        (
            (
                "Minimize the time it takes to find where a credential is stored when rotating it",
                9.0,
                3.2,
            ),
            (
                "Minimize the number of questions a new engineer asks to locate a staging "
                "secret when onboarding",
                8.2,
                2.9,
            ),
            (
                "Minimize the duration spent hunting a production secret across three vaults "
                "when a deadline is set",
                7.6,
                4.8,
            ),
            (
                "Minimize the likelihood of reading a stale credential path when several "
                "vaults hold the same name",
                8.8,
                5.4,
            ),
            (
                "Minimize the time it takes to confirm a secret exists in the expected vault "
                "when a build is queued",
                6.9,
                6.2,
            ),
        ),
    ),
    (
        JobStage.PREPARE,
        (
            (
                "Minimize the time it takes to stage a secret locally before a first deploy",
                8.6,
                3.8,
            ),
            (
                "Minimize the number of manual steps needed to prepare a service's secrets "
                "when a new service joins",
                7.9,
                4.4,
            ),
            (
                "Minimize the errors introduced while copying values from a vault into a CI store",
                9.1,
                3.0,
            ),
            (
                "Minimize the time it takes to grant a pipeline the scopes it needs before it runs",
                7.4,
                5.9,
            ),
            (
                "Minimize the cost of rehearsing a secret change in a sandbox before it "
                "reaches production",
                6.2,
                6.8,
            ),
        ),
    ),
    (
        JobStage.CONFIRM,
        (
            (
                "Minimize the time it takes to verify every service can read its secrets "
                "before a deploy",
                8.9,
                3.4,
            ),
            (
                "Minimize the number of checks a developer runs to confirm readiness before "
                "merging",
                7.7,
                4.9,
            ),
            (
                "Minimize the likelihood of a preflight that hides a missing secret when a "
                "release is approved",
                9.3,
                4.0,
            ),
            (
                "Minimize the time two teams need to agree a rotation plan is ready when a "
                "release is scheduled",
                6.8,
                6.4,
            ),
            (
                "Minimize the attempts needed to confirm permissions cover every environment "
                "before a release",
                7.1,
                5.6,
            ),
        ),
    ),
    (
        JobStage.EXECUTE,
        (
            (
                "Minimize the time it takes to propagate a changed secret to every consumer "
                "when it rotates",
                9.2,
                3.1,
            ),
            (
                "Minimize the number of services left holding an old value after a rotation "
                "completes",
                8.7,
                2.8,
            ),
            (
                "Minimize the time it takes to sync a secret to a second cluster while a "
                "deploy runs",
                9.0,
                4.2,
            ),
            (
                "Minimize the number of manual steps needed to write one secret into each "
                "service when a fleet scales",
                8.3,
                3.5,
            ),
            (
                "Minimize the likelihood of exposing plain-text keys in build logs when a "
                "pipeline fails",
                9.8,
                4.5,
            ),
        ),
    ),
    (
        JobStage.MONITOR,
        (
            (
                "Minimize the time between an expired secret and a team noticing it during a "
                "release window",
                9.4,
                2.6,
            ),
            (
                "Minimize the number of pipelines that fail on missing configuration before "
                "anyone notices during a deploy",
                8.8,
                3.3,
            ),
            (
                "Minimize the duration a service runs with a mismatched secret before "
                "monitoring surfaces it",
                7.5,
                6.7,
            ),
            (
                "Maximize the share of secret failures attributed to the right service when "
                "an alert fires",
                6.4,
                5.8,
            ),
            (
                "Minimize the time it takes to learn that a rotation stalled while an "
                "engineer is off shift",
                7.0,
                7.0,
            ),
        ),
    ),
    (
        JobStage.MODIFY,
        (
            (
                "Minimize the time it takes to correct a mismatched key after a failed deploy",
                8.5,
                3.7,
            ),
            (
                "Minimize the number of services touched when one secret name changes",
                8.1,
                4.6,
            ),
            (
                "Minimize the steps required to roll back a bad secret value after a failed deploy",
                7.3,
                5.2,
            ),
            (
                "Minimize the likelihood that fixing one service breaks another when secrets "
                "are edited by hand",
                8.0,
                6.0,
            ),
            (
                "Minimize the time it takes to re-run a pipeline after a corrected secret lands",
                6.6,
                6.9,
            ),
        ),
    ),
    (
        JobStage.CONCLUDE,
        (
            (
                "Minimize the time it takes to close a rotation after every service confirms "
                "the new value",
                5.9,
                7.4,
            ),
            (
                "Minimize the number of open questions carried into the next rotation when a "
                "change concludes",
                5.2,
                6.5,
            ),
            (
                "Maximize the share of rotations finished with an audit trail in place before "
                "the ticket closes",
                6.7,
                5.5,
            ),
            (
                "Minimize the time it takes to archive an old secret value after a rotation "
                "is accepted",
                4.8,
                7.2,
            ),
            (
                "Minimize the time it takes to rotate an expired token in a running pod "
                "before traffic drops",
                8.0,
                7.2,
            ),
        ),
    ),
)


@dataclass(frozen=True)
class _Record:
    """One research record in the study, tied to the outcome it bears on."""

    id: str
    source_name: str
    source_kind: str
    item_type: EvidenceItemType
    name: str
    content: str
    outcome_id: str
    url: str | None = None
    raw: dict[str, Any] | None = None


_RECORDS: tuple[_Record, ...] = (
    _Record(
        id="EVD-101",
        source_name="Fintech customer call 104",
        source_kind="interview",
        item_type="resource",
        name="Call 104: manual copy-paste drift",
        content=(
            "We had a junior engineer push code that broke staging because the Stripe secret "
            "wasn't copied over. Three senior engineers spent two hours on it. There has to be "
            "a better way than copy-pasting strings."
        ),
        outcome_id="O-21",
        url="https://app.gong.io/calls/104",
        raw={"severity": "high", "speaker": "Tech Lead"},
    ),
    _Record(
        id="EVD-102",
        source_name="Slack #incident-deployments",
        source_kind="manual",
        item_type="resource",
        name="Staging broke after a third rotation",
        content=(
            "Third time this week staging broke after a secret rotation. We need automated "
            "synchronization across microservices."
        ),
        outcome_id="O-22",
        url="https://workspace.slack.com/archives/C0123/p169000222",
        raw={"channel": "#incident-deployments", "severity": "critical"},
    ),
    _Record(
        id="EVD-103",
        source_name="Vault migration RFC",
        source_kind="manual",
        item_type="resource",
        name="Survey: missing env variables dominate blockers",
        content=(
            "Developer survey shows 85% of time spent on deployment blockers is caused by "
            "missing env variables in microservice pipelines."
        ),
        outcome_id="O-27",
        url="https://notion.so/org/Vault-Migration-RFC-99812",
        raw={"votes": 42},
    ),
    _Record(
        id="EVD-104",
        source_name="Platform team interview",
        source_kind="interview",
        item_type="note",
        name="Shared spreadsheet of key requirements",
        content=(
            "We keep a spreadsheet of which service needs which key. When someone edits it "
            "without telling the rest of us, the next deploy fails."
        ),
        outcome_id="O-1",
        raw={"speaker": "Tech Lead", "duration_minutes": 42},
    ),
    _Record(
        id="EVD-105",
        source_name="Site reliability interview",
        source_kind="interview",
        item_type="note",
        name="Friday rotation, Monday discovery",
        content=(
            "Last quarter we shipped a rotation on Friday and three staging services still "
            "read the old value until Monday. Nobody noticed because the pipeline logged a "
            "generic error."
        ),
        outcome_id="O-28",
        raw={"speaker": "SRE", "incident": "rotation-2291"},
    ),
    _Record(
        id="EVD-106",
        source_name="Security audit walkthrough",
        source_kind="interview",
        item_type="note",
        name="Plaintext keys in four pipeline logs",
        content=(
            "The audit found plaintext keys in build logs for four pipelines. The team could "
            "not say which service had rotated when."
        ),
        outcome_id="O-25",
        raw={"severity": "high", "framework": "SOC2"},
    ),
    _Record(
        id="EVD-107",
        source_name="New hire onboarding notes",
        source_kind="manual",
        item_type="note",
        name="Day 3: four answers to one question",
        content=(
            "Day 3 and I still cannot find the Stripe staging key. I asked four people and got "
            "four answers."
        ),
        outcome_id="O-7",
        raw={},
    ),
    _Record(
        id="EVD-108",
        source_name="Release manager interview",
        source_kind="interview",
        item_type="note",
        name="Preflight passes, secret missing",
        content=(
            "A preflight that passes tells me nothing about the one secret nobody added. I "
            "still read the diff by hand before every release."
        ),
        outcome_id="O-18",
        raw={"speaker": "Release Manager"},
    ),
    _Record(
        id="EVD-109",
        source_name="Rotation retrospective",
        source_kind="manual",
        item_type="note",
        name="One rename, six consumers",
        content=(
            "Two engineers, six services, one name change. Every consumer had to be touched "
            "separately and nobody could say when we were done."
        ),
        outcome_id="O-32",
        raw={"attendees": 5},
    ),
    _Record(
        id="EVD-110",
        source_name="Compliance officer interview",
        source_kind="interview",
        item_type="note",
        name="The trail ends at the vault",
        content=(
            "We can prove who rotated a production key, but not that every consumer picked it "
            "up. The trail ends at the vault."
        ),
        outcome_id="O-38",
        raw={"role": "Compliance"},
    ),
    _Record(
        id="EVD-111",
        source_name="Platform to payments handoff",
        source_kind="manual",
        item_type="note",
        name="SECRET_KEY versus SECRET_KEY_V2",
        content=(
            "The payments repo expects SECRET_KEY_V2 but the vault still writes SECRET_KEY. "
            "This has been true since March."
        ),
        outcome_id="O-13",
        raw={},
    ),
    _Record(
        id="EVD-112",
        source_name="DevOps lead interview",
        source_kind="interview",
        item_type="note",
        name="A stalled rotation, reported next morning",
        content=(
            "When a rotation stalls at 2am I find out from an alert the next morning, not from "
            "the pipeline."
        ),
        outcome_id="O-30",
        raw={"speaker": "DevOps Lead"},
    ),
)


@dataclass(frozen=True)
class DemoLoadResult:
    """What a load submitted: the job the rows hang off, and rows per entity."""

    job_id: str
    counts: dict[str, int]


def fixture_rows(job_id: str = DEMO_JOB_ID) -> dict[str, list[Any]]:
    """Return the study as typed rows, all labeled ``origin="demo"``.

    ``job_id`` re-parents every row, so the same study can be attached to a job
    the customer already has instead of the stand-in. Ids never change: that is
    what makes a second load a no-op rather than a copy.
    """
    steps: list[Step] = []
    outcomes: list[Outcome] = []
    outcome_number = 0
    for stage_position, (stage, statements) in enumerate(_OUTCOME_SETS, start=1):
        step_id = f"STP-{stage_position}"
        steps.append(
            Step(
                id=step_id,
                job_id=job_id,
                name=_STEP_NAMES[stage_position - 1],
                order=stage_position,
                stage=stage,
                stage_index=JOB_STAGE_ORDER.index(stage) + 1,
                origin="demo",
            )
        )
        for statement, importance, satisfaction in statements:
            outcome_number += 1
            outcomes.append(
                Outcome(
                    id=f"O-{outcome_number}",
                    job_id=job_id,
                    step_id=step_id,
                    statement=" ".join(statement.split()),
                    importance=importance,
                    satisfaction=satisfaction,
                    opportunity_score=compute_opportunity_score(importance, satisfaction),
                    origin="demo",
                )
            )
    #: A record inherits its step from the outcome it quotes, so the two can
    #: never disagree — the service refuses evidence that links to both.
    step_of_outcome = {outcome.id: outcome.step_id for outcome in outcomes}
    evidence = [
        Evidence(
            id=record.id,
            source_name=record.source_name,
            source_kind=record.source_kind,
            item_type=record.item_type,
            name=record.name,
            content=record.content,
            url=record.url,
            raw=dict(record.raw or {}),
            job_id=job_id,
            step_id=step_of_outcome[record.outcome_id],
            outcome_id=record.outcome_id,
            origin="demo",
        )
        for record in _RECORDS
    ]
    return {
        "jobs": [
            Job(
                id=job_id,
                name=DEMO_JOB_NAME,
                description=DEMO_JOB_DESCRIPTION,
                origin="demo",
            )
        ],
        "steps": steps,
        "outcomes": outcomes,
        "evidence": evidence,
    }


def load_demo_workspace(service: ODIService, *, job_id: str | None = None) -> DemoLoadResult:
    """Write the study through ``service``, creating nothing twice.

    With no ``job_id`` the study arrives as its own Job. With one, the rows are
    attached to that existing Job and no demo Job is written, so the customer's
    own job keeps its name. Every write goes through the same service methods
    the MCP tools use: the outcome statement validator runs, and a row that is
    already there unchanged is left alone instead of appended again.
    """
    repository: Repository = service.repo
    target = job_id or DEMO_JOB_ID
    if job_id is not None and repository.get_job(job_id) is None:
        raise JobNotFoundError(job_id)

    rows = fixture_rows(target)
    submitted: dict[str, int] = {}
    if job_id is None:
        for job in rows["jobs"]:
            service.add_job(job.name, job.description, id=job.id, origin=job.origin)
    submitted["jobs"] = len(rows["jobs"]) if job_id is None else 0
    for step in rows["steps"]:
        service.add_step(
            step.job_id,
            step.name,
            step.order,
            step.stage,
            allow_empty_job_map=True,
            id=step.id,
            origin=step.origin,
        )
    submitted["steps"] = len(rows["steps"])
    for outcome in rows["outcomes"]:
        service.add_outcome(
            outcome.job_id,
            outcome.statement,
            importance=float(outcome.importance or 0.0),
            satisfaction=float(outcome.satisfaction or 0.0),
            step_id=outcome.step_id,
            id=outcome.id,
            origin=outcome.origin,
        )
    submitted["outcomes"] = len(rows["outcomes"])
    for item in rows["evidence"]:
        service.add_evidence(
            item.source_name,
            item.source_kind,
            item.name,
            item.content,
            item.item_type,
            url=item.url,
            raw=item.raw,
            job_id=item.job_id,
            step_id=item.step_id,
            outcome_id=item.outcome_id,
            id=item.id,
            origin=item.origin,
        )
    submitted["evidence"] = len(rows["evidence"])
    return DemoLoadResult(job_id=target, counts=submitted)
