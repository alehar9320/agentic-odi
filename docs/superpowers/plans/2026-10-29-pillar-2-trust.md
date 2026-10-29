# Pillar 2 — Trust: A Number Means What It Says — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every ODI score carry its sample, its method, its band and its limitations, so a ranking can be challenged without turning unknowns into facts.

**Architecture:** The pillar adds fields to the existing `Outcome` model and new entities alongside it, plumbed through the repository/service/contract/MCP/CLI/studio-api/studio-types spine the repository already has. `ODIService` stays the single write path; the SQLite append-only event log stays the only persistence mechanism; `contract.TOOL_SPECS` stays the single source of truth for the MCP surface. No second aggregator, ranking function or importer is introduced.

**Tech Stack:** Python 3.10+, Pydantic v2, FastMCP, SQLite (`IntentStore` append-only event log), Typer, pytest/pytest-asyncio (strict), ruff, mypy, React + Vite (`apps/studio`).

**Spec:** `docs/superpowers/specs/2026-10-29-pillar-2-trust-design.md`

## Global Constraints

- Python `>=3.10`; ruff line-length 100; ruff select `["E4","E7","E9","F","I","UP","B","BLE"]`.
- Opportunity Score = `importance + max(importance - satisfaction, 0)` — always via `models.compute_opportunity_score`.
- `importance`/`satisfaction` valid range `1.0`–`10.0`; a sample count is `int | None` with `ge=1`.
- **No fabricated data.** A missing score/sample/band is unknown, never `0`, `1` or a default that asserts a sample nobody took.
- **AI output is a proposal; a human accepts it.**
- **Persistence checklist** (every new field/entity): `models.py`, `repository.py` (Protocol + `InMemoryRepository`), `sqlite_repository._apply_event`, `remote.py`/`schema.py`, `services.py`, `contract.TOOL_SPECS`, `mcp_server.py`, CLI, studio-api `schemas.py`, `apps/studio/src/types.ts`.
- **Contract synchronization:** `contract.py`, `mcp_server.py` and the `get_capabilities` string move together; `tests/contract/test_mcp_contract.py` enforces it.
- **Docs in the same change:** `README.md` (new command/package), `docs/cli.md` (new flag), `docs/living-studio.md` (new surface), `docs/roadmap.md` (ticked milestone item).
- Branch from `origin/main`. Run tests with `uv run pytest` from the repo root.
- Tests are atomic, named for the behavior they pin, and use in-memory stores; never touch `~/.agentic-odi/odi.db`.

## Review Focus

Failure modes most likely to bite a user, each pinned by a test in its owning task:

1. **Unknown vs zero** — an outcome with no recorded sample must never display or rank as `n=0` or `n=1` (Tasks 1, 2, 5, 8).
2. **Estimate with a real sample** — `method=estimate` with `n>1` asserts people were asked who were not; it must fail before mutation (Tasks 1, 3, 4).
3. **Replay divergence** — a field added on one link of the persistence checklist but not another must fail a parity test, not silently differ between in-memory and SQLite after reload (Tasks 1, 3, 6).
4. **Partial update validation** — switching an existing survey to `estimate` must validate the *whole* resulting record, not just the patched fields (Task 3).
5. **Backfill idempotence** — replaying or re-running the backfill must not add duplicate events or change original scores (Tasks 3, 6).

---

## File Structure

**core/** (`packages/core/src/agentic_odi_core/`)
- `models.py` — `Outcome` gains `importance_n`, `satisfaction_n`, `score_method`; validator.
- `repository.py` — no new methods for B1 (fields travel on `Outcome`); ranking untouched.
- `sqlite_repository.py` — `OUTCOME_METHOD_BACKFILLED` branch in `_apply_event`; idempotent backfill.
- `services.py` — validate the whole resulting record on create and partial update.
- `contract.py` — `add_outcome`/`update_outcome` argument tuples + `get_capabilities` summary.
- `schema.py` — `Outcome` schema picks up the fields automatically (no code change; asserted).
- `__init__.py` — export any new literal/constant.

**apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py** — new optional args on `add_outcome`/`update_outcome`.

**apps/cli/src/agentic_odi_cli/desired_outcomes.py** — `--importance-n`, `--satisfaction-n`, `--method` flags on add/update; render line.

**apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py** — optional fields on add/update request models.

**apps/studio/src/types.ts** — `Outcome` interface gains the three fields.

**Tests**
- `packages/core/tests/test_outcome_method.py` (new)
- `packages/core/tests/test_persistence_parity.py` (new)
- `tests/contract/test_mcp_contract.py` (existing; gains assertions)
- `apps/cli/tests/test_desired_outcomes_cli.py` (existing; extended)
- `apps/studio-api/tests/test_studio_manual_crud.py` (existing; extended)

---

## Increment order

Land in this order; each is its own PR and its own reviewable slice. Tasks 1–8 below
fully specify **B1 (ALH-24)**, the only increment with no prerequisite and no open
decision blocker. The later increments are listed with their gate and owner; they are
planned in detail when their gate clears (see the spec's decision-blocker table).

| Order | Increment | Owner | Gate |
|---|---|---|---|
| 1 | B1 sample/method metadata | ALH-24 | none — **specified below** |
| 2 | B2 survey import + aggregate | ALH-25 | import-policy decision |
| 3 | B2.2 dry-run/report/match | ALH-156 | import-policy decision |
| 4 | B3 pure interval | ALH-26 | bootstrap-convention decision |
| 5 | B3.1 retained paired inputs | ALH-178 | retention-policy decision |
| 6 | B3.2 persist provenance | ALH-179 | inherits 4 + 5 |
| 7 | B4 ranking + landscape | ALH-27 | needs 5, 6 |
| 8 | B4.1 confidence table | ALH-180 | confidence-table decision |
| 9 | B4.2 `odi top` | ALH-190 | needs 7, 8, 6 |
| 10 | B6 snapshot writer | ALH-29 | needs B1 |
| 11 | B6.1 history/deltas | ALH-203 | delta-semantics decision |
| 12 | M2/M3/M4 slices | ALH-71… | per-issue gates |

---

## Task 1: Add count/method fields to the `Outcome` model

**Files:**
- Modify: `packages/core/src/agentic_odi_core/models.py` (`Outcome`)
- Test: `packages/core/tests/test_outcome_method.py` (new)

**Interfaces:**
- Produces: `Outcome.importance_n: int | None`, `Outcome.satisfaction_n: int | None`,
  `Outcome.score_method: Literal["estimate","survey","import"]` (default `"estimate"`).

- [x] **Step 1: Write the failing test**

```python
"""Sample size and method travel with an outcome score."""

import pytest
from pydantic import ValidationError

from agentic_odi_core.models import Outcome


def _outcome(**overrides):
    base = {"job_id": "job-1", "statement": "Minimize the time it takes to onboard a new engineer.",
            "importance": 8.0, "satisfaction": 6.0}
    base.update(overrides)
    return Outcome(**base)


def test_counts_default_to_none_not_zero_or_one():
    outcome = _outcome()
    assert outcome.importance_n is None
    assert outcome.satisfaction_n is None
    assert outcome.score_method == "estimate"


def test_a_count_of_zero_is_rejected():
    with pytest.raises(ValidationError):
        _outcome(importance_n=0)


def test_a_negative_count_is_rejected():
    with pytest.raises(ValidationError):
        _outcome(satisfaction_n=-3)


def test_a_non_integer_count_is_rejected():
    with pytest.raises(ValidationError):
        _outcome(importance_n=1.5)


def test_a_count_above_one_requires_a_non_estimate_method():
    with pytest.raises(ValidationError):
        _outcome(importance_n=40, score_method="estimate")


def test_a_survey_with_a_count_is_accepted():
    outcome = _outcome(importance_n=40, satisfaction_n=40, score_method="survey")
    assert outcome.score_method == "survey"


def test_an_estimate_with_unknown_counts_is_accepted():
    outcome = _outcome(score_method="estimate")
    assert outcome.importance_n is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_outcome_method.py -q`
Expected: FAIL — `Outcome` has no field `importance_n`.

- [x] **Step 3: Implement the fields and validator**

In `models.py`, add a module-level literal alias and extend `Outcome`:

```python
ScoreMethod = Literal["estimate", "survey", "import"]
```

```python
class Outcome(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The ID of the Job this outcome relates to")
    step_id: str | None = Field(None, description="The ID of the specific Step, if applicable")
    statement: str = Field(
        ..., description="The desired outcome statement (e.g., 'Minimize the time it takes to...')"
    )
    importance: float | None = Field(
        default=None, ge=1.0, le=10.0, description="Importance score (1-10)"
    )
    satisfaction: float | None = Field(
        default=None, ge=1.0, le=10.0, description="Current satisfaction score (1-10)"
    )
    opportunity_score: float | None = Field(
        None, description="Opportunity score (Importance + max(Importance - Satisfaction, 0))"
    )
    importance_n: int | None = Field(
        default=None, ge=1, description="People behind the importance score, when known"
    )
    satisfaction_n: int | None = Field(
        default=None, ge=1, description="People behind the satisfaction score, when known"
    )
    score_method: ScoreMethod = Field(
        default="estimate",
        description="How the score was obtained: a one-person estimate, a survey, or an import",
    )

    @model_validator(mode="after")
    def _count_requires_a_sample(self) -> "Outcome":
        # A count above one means people were asked; an estimate cannot have asked them.
        if self.score_method == "estimate" and (
            (self.importance_n or 0) > 1 or (self.satisfaction_n or 0) > 1
        ):
            raise ValueError(
                "score_method 'estimate' cannot carry a sample count above 1; "
                "use 'survey' or 'import' when people were asked"
            )
        return self
```

Add `model_validator` to the pydantic import at the top of `models.py`.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_outcome_method.py -q`
Expected: PASS (7 passed).

- [x] **Step 5: Run the core suite for regressions**

Run: `uv run pytest packages/core -q`
Expected: PASS. Existing `Outcome` construction is unaffected because all three fields are optional/defaulted.

- [x] **Step 6: Commit**

```bash
git add packages/core/src/agentic_odi_core/models.py packages/core/tests/test_outcome_method.py
git commit -m "feat(core): carry sample size and method on every outcome score"
```

---

## Task 2: Validate the whole record on the service write path

**Files:**
- Modify: `packages/core/src/agentic_odi_core/services.py` (`add_outcome`, `update_outcome`)
- Test: `packages/core/tests/test_service.py` (extend)

**Interfaces:**
- Consumes: `Outcome.score_method`, `importance_n`, `satisfaction_n` (Task 1).
- Produces: `ODIService.add_outcome(..., importance_n=None, satisfaction_n=None, score_method="estimate")`
  and `ODIService.update_outcome(...)` that validates the resulting whole record.

- [x] **Step 1: Write the failing tests**

```python
def test_add_outcome_rejects_an_estimate_with_a_count(service, job_id):
    with pytest.raises(ValueOutOfRangeError):
        service.add_outcome(
            job_id, "Minimize the time it takes to onboard a new engineer.",
            importance=8.0, satisfaction=6.0, importance_n=40,
        )


def test_add_outcome_accepts_a_survey_with_counts(service, job_id):
    outcome = service.add_outcome(
        job_id, "Minimize the time it takes to onboard a new engineer.",
        importance=8.0, satisfaction=6.0,
        importance_n=40, satisfaction_n=40, score_method="survey",
    )
    assert outcome.importance_n == 40
    assert outcome.score_method == "survey"


def test_update_switching_survey_to_estimate_validates_the_whole_record(service, job_id):
    outcome = service.add_outcome(
        job_id, "Minimize the time it takes to onboard a new engineer.",
        importance=8.0, satisfaction=6.0,
        importance_n=40, satisfaction_n=40, score_method="survey",
    )
    with pytest.raises(ValueOutOfRangeError):
        service.update_outcome(outcome.id, {"score_method": "estimate"})


def test_update_clearing_a_count_keeps_the_method(service, job_id):
    outcome = service.add_outcome(
        job_id, "Minimize the time it takes to onboard a new engineer.",
        importance=8.0, satisfaction=6.0,
        importance_n=40, satisfaction_n=40, score_method="survey",
    )
    updated = service.update_outcome(outcome.id, {"importance_n": None})
    assert updated.importance_n is None
    assert updated.score_method == "survey"
```

Add a `service`/`job_id` fixture if the module does not already provide one (it does — follow the existing pattern in `test_service.py`).

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_service.py -k "count or survey_to_estimate" -q`
Expected: FAIL — `add_outcome` has no `importance_n` parameter.

- [x] **Step 3: Implement**

Extend `add_outcome` with the three keyword arguments and pass them into `Outcome(...)`.
Add a shared guard so the same rule holds on both paths. Raise `ValueOutOfRangeError`
with the same message the model uses:

```python
def _reject_estimate_with_a_sample(method: str, importance_n: int | None, satisfaction_n: int | None) -> None:
    if method == "estimate" and ((importance_n or 0) > 1 or (satisfaction_n or 0) > 1):
        raise ValueOutOfRangeError(
            "score_method 'estimate' cannot carry a sample count above 1; "
            "use 'survey' or 'import' when people were asked"
        )
```

In `add_outcome`, call it before constructing the `Outcome`. In `update_outcome`,
after merging `updates` onto the existing outcome, validate the *whole* merged record
(construct an `Outcome` from the merged dict, or call `_reject_estimate_with_a_sample`
with the merged method and counts) **before** writing, so a partial patch cannot
produce an invalid stored record.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_service.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add packages/core/src/agentic_odi_core/services.py packages/core/tests/test_service.py
git commit -m "feat(core): validate sample/method on the whole record, both write paths"
```

---

## Task 3: Replay and idempotent backfill in SQLite

**Files:**
- Modify: `packages/core/src/agentic_odi_core/sqlite_repository.py`
- Test: `packages/core/tests/test_sqlite_repository.py` (extend)

**Interfaces:**
- Consumes: the new `Outcome` fields (Task 1).
- Produces: an `OUTCOME_METHOD_BACKFILLED` event type replayed by `_apply_event`;
  legacy rows read back as `estimate`/`n=None`; re-running the backfill adds no
  duplicate events.

- [x] **Step 1: Write the failing tests**

```python
def test_legacy_outcome_reads_back_as_an_estimate(tmp_path):
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    outcome = repo.add_outcome(Outcome(job_id="j", statement=_STMT, importance=8.0, satisfaction=6.0))
    repo.reload()
    assert repo.get_outcome(outcome.id).score_method == "estimate"
    assert repo.get_outcome(outcome.id).importance_n is None


def test_backfill_is_idempotent_across_reloads(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    repo.add_outcome(Outcome(job_id="j", statement=_STMT, importance=8.0, satisfaction=6.0))
    repo.reload()
    repo.reload()
    events = [e for e in repo.store.get_stream() if e["type"] == "OUTCOME_METHOD_BACKFILLED"]
    assert len(events) == len({e["payload"]["id"] for e in events})


def test_backfill_preserves_the_original_score(tmp_path):
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    outcome = repo.add_outcome(Outcome(job_id="j", statement=_STMT, importance=8.0, satisfaction=6.0))
    repo.reload()
    reloaded = repo.get_outcome(outcome.id)
    assert (reloaded.importance, reloaded.satisfaction) == (8.0, 6.0)
    assert reloaded.opportunity_score == outcome.opportunity_score
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_sqlite_repository.py -k "method_backfill or legacy_outcome_reads" -q`
Expected: FAIL — no `OUTCOME_METHOD_BACKFILLED` branch.

- [x] **Step 3: Implement**

In `_apply_event`, add:

```python
elif et == "OUTCOME_METHOD_BACKFILLED":
    self._merge_updates(self.outcomes, p, Outcome)
```

Add a `_backfill_outcome_method` step, modelled on `_backfill_legacy_outcomes`, that
writes one `OUTCOME_METHOD_BACKFILLED` event per outcome whose stored payload lacks the
new fields, setting `score_method="estimate"` and leaving `importance_n`/`satisfaction_n`
absent (`None`). Because `_load_snapshot` already replays the stream, a row that already
carries `score_method` (i.e. was written after this change) must not be re-emitted —
the event is skipped when the model already has the field. Guard with the existing
`self._backfilled` flag so a single process does not repeat it.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_sqlite_repository.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add packages/core/src/agentic_odi_core/sqlite_repository.py packages/core/tests/test_sqlite_repository.py
git commit -m "feat(core): backfill legacy outcomes to estimate via an auditable event"
```

---

## Task 4: Plumb the fields through the MCP contract

**Files:**
- Modify: `packages/core/src/agentic_odi_core/contract.py` (`TOOL_SPECS`)
- Modify: `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` (`add_outcome`, `update_outcome`)
- Test: `tests/contract/test_mcp_contract.py` (extend), `apps/mcp-server/tests/test_odi.py` (extend)

**Interfaces:**
- Consumes: `ODIService.add_outcome`/`update_outcome` (Task 2).
- Produces: MCP tools accept `importance_n`, `satisfaction_n`, `score_method`; `TOOL_SPECS`
  argument tuples match; the `get_capabilities` summary still renders.

- [x] **Step 1: Write the failing contract assertion**

In `tests/contract/test_mcp_contract.py`, the existing test already asserts
`set(schema["properties"]) == set(spec.arguments)` for every tool. Add an explicit
regression so the intent is visible:

```python
def test_add_outcome_exposes_sample_metadata():
    spec = TOOL_SPECS["add_outcome"]
    assert {"importance_n", "satisfaction_n", "score_method"} <= set(spec.arguments)


def test_update_outcome_exposes_sample_metadata():
    spec = TOOL_SPECS["update_outcome"]
    assert {"importance_n", "satisfaction_n", "score_method"} <= set(spec.arguments)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/contract/test_mcp_contract.py -q`
Expected: FAIL — the argument tuples do not include the new names.

- [x] **Step 3: Implement**

In `contract.py`, extend the `add_outcome` `arguments` tuple to
`("job_id", "statement", "importance", "satisfaction", "step_id", "importance_n", "satisfaction_n", "score_method")`
and the `update_outcome` tuple likewise (it already carries `step_id`). Update the
`summary`/`returns` text only if it becomes inaccurate.

In `mcp_server.py`, add the three optional parameters to `add_outcome` and
`update_outcome`, forward them to the service, and map `ValueOutOfRangeError` to the
existing error string. `get_capabilities` is generated from `TOOL_SPECS`, so it needs
no manual edit — but run the capability-manifest test to confirm.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/contract apps/mcp-server -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add packages/core/src/agentic_odi_core/contract.py apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py tests/contract/test_mcp_contract.py apps/mcp-server/tests/test_odi.py
git commit -m "feat(mcp): expose sample and method on the outcome tools"
```

---

## Task 5: CLI flags and rendering

**Files:**
- Modify: `apps/cli/src/agentic_odi_cli/desired_outcomes.py`
- Modify: `apps/cli/src/agentic_odi_cli/render.py` (render the method/sample line)
- Modify: `docs/cli.md`
- Test: `apps/cli/tests/test_desired_outcomes_cli.py` (extend)

**Interfaces:**
- Consumes: MCP tools (Task 4).
- Produces: `odi desired-outcomes add|update --importance-n --satisfaction-n --method`;
  the readable renderer shows `est.` or `n=40 (survey)`.

- [x] **Step 1: Write the failing tests**

```python
def test_add_outcome_passes_sample_metadata(runner, ...):
    result = runner.invoke(app, ["desired-outcomes", "add", "--job-id", job, "--statement", _STMT,
                                 "--importance", "8", "--satisfaction", "6",
                                 "--importance-n", "40", "--satisfaction-n", "40", "--method", "survey"])
    assert result.exit_code == 0


def test_add_outcome_rejects_an_estimate_with_a_count(runner, ...):
    result = runner.invoke(app, ["desired-outcomes", "add", ..., "--importance-n", "40"])
    assert result.exit_code == 1


def test_render_shows_est_for_unknown_counts():
    line = render_outcome({"statement": _STMT, "importance": 8, "satisfaction": 6,
                           "opportunity_score": 10, "score_method": "estimate"}, as_json=False)
    assert "est." in line


def test_render_shows_n_and_method_when_present():
    line = render_outcome({"statement": _STMT, "importance": 8, "satisfaction": 6,
                           "opportunity_score": 10, "score_method": "survey",
                           "importance_n": 40, "satisfaction_n": 40}, as_json=False)
    assert "n=40" in line and "survey" in line


def test_render_shows_both_counts_when_they_differ():
    line = render_outcome({"statement": _STMT, "importance": 8, "satisfaction": 6,
                           "opportunity_score": 10, "score_method": "survey",
                           "importance_n": 40, "satisfaction_n": 12}, as_json=False)
    assert "40" in line and "12" in line
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/cli/tests/test_desired_outcomes_cli.py -k "sample or est or both_counts" -q`
Expected: FAIL — the flags do not exist.

- [x] **Step 3: Implement**

Add `importance_n: int | None`, `satisfaction_n: int | None`, `method: str | None`
Typer options to `add` and `update`, forwarding them as `importance_n`,
`satisfaction_n`, `score_method`. Add the method/sample line to `render_outcome`,
printing `est.` when the method is `estimate` or the counts are unknown, and
`n=<importance_n>/<satisfaction_n>` (or a single `n=` when equal) plus the method
otherwise. Add the flags to `docs/cli.md`.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/cli -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/cli/src/agentic_odi_cli/desired_outcomes.py apps/cli/src/agentic_odi_cli/render.py apps/cli/tests/test_desired_outcomes_cli.py docs/cli.md
git commit -m "feat(cli): set and show an outcome's sample and method"
```

---

## Task 6: In-memory/SQLite parity test

**Files:**
- Test: `packages/core/tests/test_persistence_parity.py` (new)

**Interfaces:**
- Consumes: Tasks 1–3.

- [x] **Step 1: Write the failing test**

```python
"""A field added on one persistence link must exist on all of them."""

import pytest
from agentic_odi_core.models import Outcome
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.sqlite_repository import SQLiteRepository


def _seed(repo):
    return repo.add_outcome(Outcome(
        job_id="job-1",
        statement="Minimize the time it takes to onboard a new engineer.",
        importance=8.0, satisfaction=6.0,
        importance_n=40, satisfaction_n=40, score_method="survey",
    ))


@pytest.mark.parametrize("factory", ["memory", "sqlite"])
def test_sample_metadata_survives_every_repository(factory, tmp_path):
    repo = InMemoryRepository() if factory == "memory" else SQLiteRepository(str(tmp_path / "odi.db"))
    outcome = _seed(repo)
    repo.reload()
    loaded = repo.get_outcome(outcome.id)
    assert (loaded.importance_n, loaded.satisfaction_n, loaded.score_method) == (40, 40, "survey")
```

- [x] **Step 2: Run test to verify it fails or passes**

Run: `uv run pytest packages/core/tests/test_persistence_parity.py -q`
Expected: PASS once Tasks 1–3 are in. If it fails on SQLite, the event payload is not
carrying the fields — fix `add_outcome`/`_apply_event`, do not weaken the test.

- [x] **Step 3: Commit**

```bash
git add packages/core/tests/test_persistence_parity.py
git commit -m "test(core): pin in-memory/SQLite parity for outcome sample metadata"
```

---

## Task 7: Studio API schema and Studio types

**Files:**
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py`
- Modify: `apps/studio/src/types.ts`
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/router.py` (pass through)
- Test: `apps/studio-api/tests/test_studio_manual_crud.py` (extend)

**Interfaces:**
- Consumes: MCP tools (Task 4).

- [x] **Step 1: Write the failing test**

```python
def test_manual_outcome_accepts_sample_metadata(client, ...):
    body = {"job_id": job, "statement": _STMT, "importance": 8, "satisfaction": 6,
            "importance_n": 40, "satisfaction_n": 40, "score_method": "survey"}
    response = client.post("/studio/outcomes", json=body)
    assert response.status_code == 200
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/studio-api/tests/test_studio_manual_crud.py -k sample -q`
Expected: FAIL — the request model rejects/ignores the fields.

- [x] **Step 3: Implement**

Add `importance_n: int | None = Field(default=None, ge=1)`,
`satisfaction_n: int | None = Field(default=None, ge=1)`,
`score_method: Literal["estimate","survey","import"] = "estimate"` to
`AddOutcomeRequest` and the optional variants to `UpdateOutcomeRequest`. Forward them in
`router.py`. Add the three fields to the `Outcome` interface in
`apps/studio/src/types.ts`. Confirm `npm --prefix apps/studio test -- --run` and the
TypeScript build still pass.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/studio-api -q && npm --prefix apps/studio test -- --run`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py apps/studio-api/src/agentic_odi_studio_api/studio/router.py apps/studio-api/tests/test_studio_manual_crud.py apps/studio/src/types.ts
git commit -m "feat(studio): carry outcome sample metadata through the sidecar and types"
```

---

## Task 8: Docs, roadmap and full verification

**Files:**
- Modify: `README.md` (if a command/package changed), `docs/living-studio.md` (if a surface changed)
- Test: the whole suite.

- [x] **Step 1: Update docs in the same change**

Tick the roadmap item if this completes one; note the new fields where outcomes are
documented. Keep `README.md` short and push detail to `docs/`.

- [x] **Step 2: Full verification**

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy apps packages
npm --prefix apps/studio test -- --run
```

Expected: all pass; coverage stays at or above the `fail_under = 89` floor.

- [x] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: record outcome sample/method in the trust surfaces"
```

---

## Acceptance criteria (B1 / ALH-24)

- [x] `importance_n=0` is rejected.
- [x] An existing row reads back as `estimate`/`n=None` after migration.
- [x] The landscape shows `est.` or `n=40`.
- [x] The contract test sees the new optional arguments.
- [x] Both dimensions reject zero, negative and non-integer counts; omitted counts remain `None`, not 1 or 0.
- [x] Creating or partially updating an outcome with `method=estimate` and either count above 1 fails before mutation; switching an existing survey to estimate validates the resulting whole record.
- [x] A backfill can be rerun without duplicate events; replay and reload preserve the same fields and original scores.
- [x] CLI, MCP, API, remote/schema and Studio types round-trip omitted and provided metadata consistently; differing counts display both.
- [x] Legacy unknown counts render as unknown/estimated; no consumer describes them as a one-person survey.

## Later increments (gate-first)

Each later increment is planned in full only after its decision blocker clears, to
avoid encoding an unapproved convention as code. When its gate clears:

1. Re-read the owning issue; its "What to build" is the task list.
2. Apply the persistence checklist in the Global Constraints.
3. Add a `-k <selector>` focused test module and the full-suite gate.
4. Add a `## Task N` block to this plan in the same style as Tasks 1–8.

Do not start B3 (interval) before the bootstrap convention is approved, B4 before B3
lands, B6.1 before the delta semantics are approved, or M2-19 (blind scoring) before
its trusted-viewer authorization decision.

## Seams added ahead of the gates

`packages/core/src/agentic_odi_core/trust.py` names the contract each blocked
increment must satisfy, without encoding an unapproved convention:

- `OpportunityInterval` and `opportunity_interval` (B3 — bootstrap convention).
- `classify_confidence` (B4.1 — confidence table).
- `OutcomeDelta` / `DeltaDirection` and `outcome_delta` (B6.1 — delta semantics).

Each callable raises `TrustContractPendingError` naming the blocking decision
instead of returning a fabricated band, class or direction; `test_trust_seams.py`
pins the refusal. When a gate clears, replace the raise with the approved
implementation and drop the corresponding seam test.

The B6.1 read surface is partly present: `desired-outcomes history` and
`get_outcome_history` replay the recorded snapshots, and `--why` records the
reason on the snapshot. `outcome_delta` and the delta-driven rendering stay
behind the seam until the baseline/direction decision is approved.
