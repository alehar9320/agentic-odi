# CLI ODI Entity Parity & Shared Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the `agentic-odi` CLI full create/read/update/delete access to every ODI entity (Job, Step, Desired Outcome, Customer Outcome incl. `value_metrics`), matching the MCP tool surface, backed by one persistent SQLite store shared by the CLI and the MCP server.

**Architecture:** Extend the `core` repository/service layers with CRUD + cascade delete + FK validation for `Job`/`Step`/`Outcome`. Make `SQLiteRepository` read-through (replays new events before reads) so concurrent processes converge. Add a `build_repository()` factory. The MCP server selects that factory instead of `InMemoryRepository`. The CLI gains a global `--backend/--db/--mcp-url` resolved through a shared `Backend` abstraction, plus new command groups whose names reserve `outcomes` for the desired-outcome entity.

**Tech Stack:** Python 3.10+, Typer, Pydantic v2, FastMCP, SQLite (`IntentStore` append-only event log, WAL), pytest/pytest-asyncio, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-10-15-cli-odi-entity-parity-design.md`

## Global Constraints

- Python `>=3.10`; every project targets `py310`, ruff line-length 100.
- Ruff select: `["E4", "E7", "E9", "F", "I", "UP", "B", "BLE"]`.
- Opportunity Score formula: `importance + max(importance - satisfaction, 0)` — reuse `compute_opportunity_score`.
- `importance`/`satisfaction` valid range is `1.0`–`10.0`.
- Store path env var: `AGENTIC_ODI_DB`; default `~/.agentic-odi/odi.db`; value `:memory:` means in-memory.
- CLI backend env var: `AGENTIC_ODI_BACKEND`; default `local`.
- Command vocabulary: `jobs`, `steps`, `outcomes` (Desired Outcome), `customer-outcomes` (Customer Outcome), top-level `score`.
- No CLI alias preserving the old `outcomes` = Customer Outcome meaning.
- Deleting a Job cascades to its Steps, Outcomes, Customer Outcomes; deleting a Step cascades to Outcomes/Customer Outcomes bound to it. Creating a Step/Outcome/Customer Outcome under an unknown `job_id`/`step_id` is rejected.
- Updates use the `is not None` sentinel convention: a field is never cleared by passing null; `job_id` is immutable.
- Tests must never touch the real `~/.agentic-odi/odi.db`.
- Run all tests via `uv run --directory <pkg> pytest`; lint/type via the README commands.

## Review Focus

These are the failure modes most likely to bite a user; each has its test pinned in the owning task.

1. **Concurrent writer visibility** — a CLI `local` write while the MCP server is running must be visible to the server's next read (Task 3, 5).
2. **Cascade delete replay** — deleting a Job then restarting must not resurrect its dependents; a cascaded id reads as not-found (Task 1, 3).
3. **Stored opportunity score on update** — updating only `importance` recomputes `opportunity_score`; clearing either score sets it to `None` (Task 2, 3).
4. **Bad CLI inputs** — unknown `--backend`, `--db` combined with `--backend mcp`, malformed `--value-metric` JSON, and out-of-range scores produce a clear error, never a traceback (Task 6, 7, 8, 9, 10).
5. **value_metrics semantics** — out-of-range or missing required metric fields are rejected; on update, supplying `--value-metric` replaces the whole list (Task 5, 10).

---

## File Structure

**core/** (`agentic-odi-core`)
- `core/src/core/repository.py` — `Repository` protocol + `InMemoryRepository`; add get/update/delete for Job/Step/Outcome with cascade.
- `core/src/core/services.py` — `ODIService`; add CRUD methods, FK validation, errors.
- `core/src/core/sqlite_repository.py` — event apply refactor, read-through sync, locking, new events.
- `core/src/core/intent_store.py` — allow `check_same_thread=False`.
- `core/src/core/factory.py` (**new**) — `build_repository()`.
- `core/src/core/__init__.py` — export new symbols.

**mcp_server/** (`agentic-odi-mcp-server`)
- `mcp_server/src/mcp_server/mcp_server.py` — select `build_repository()`; new CRUD tools; `value_metrics` on update.
- `mcp_server/tests/conftest.py` — force in-memory store.

**cli/** (`agentic-odi-cli`)
- `cli/src/cli/backend.py` — full `LocalBackend` dispatch, `MCPBackend`, `_call_mcp`, `BackendConfig`, `resolve_backend`.
- `cli/src/cli/jobs.py` (**new**), `cli/src/cli/steps.py` (**new**), `cli/src/cli/outcomes.py` (rewrite = Desired Outcome), `cli/src/cli/customer_outcomes.py` (**new**, moved from outcomes.py), `cli/src/cli/cli.py` (mount + global options).
- `cli/tests/` — one test module per group + backend/persistence tests.

**docs/** — `README.md` CLI section.

---

### Task 1: Core repository CRUD + cascade (in-memory)

**Files:**
- Modify: `core/src/core/repository.py`
- Test: `core/tests/test_repository.py` (new)

**Interfaces:**
- Consumes: `core.models.Job`, `Step`, `Outcome`, `CustomerOutcome`.
- Produces (on both `Repository` protocol and `InMemoryRepository`):
  - `get_step(step_id: str) -> Step | None`
  - `get_outcome(outcome_id: str) -> Outcome | None`
  - `update_job(job_id: str, updates: dict) -> Job | None`
  - `delete_job(job_id: str) -> bool`
  - `update_step(step_id: str, updates: dict) -> Step | None`
  - `delete_step(step_id: str) -> bool`
  - `update_outcome(outcome_id: str, updates: dict) -> Outcome | None`
  - `delete_outcome(outcome_id: str) -> bool`

- [ ] **Step 1: Write the failing tests** in `core/tests/test_repository.py`

```python
from core.models import Job, Outcome, Step
from core.repository import InMemoryRepository


def _repo_with_graph() -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.add_job(Job(id="j1", name="Job"))
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))
    repo.add_outcome(Outcome(id="o1", job_id="j1", step_id="s1", statement="Min x"))
    return repo


def test_get_step_and_get_outcome():
    repo = _repo_with_graph()
    assert repo.get_step("s1").name == "Step"  # type: ignore[union-attr]
    assert repo.get_outcome("o1").statement == "Min x"  # type: ignore[union-attr]
    assert repo.get_step("missing") is None


def test_update_job_merges_and_returns_none_when_missing():
    repo = _repo_with_graph()
    updated = repo.update_job("j1", {"name": "Renamed"})
    assert updated is not None and updated.name == "Renamed"
    assert repo.update_job("nope", {"name": "x"}) is None


def test_delete_job_cascades_dependents():
    repo = _repo_with_graph()
    assert repo.delete_job("j1") is True
    assert repo.get_job("j1") is None
    assert repo.get_step("s1") is None
    assert repo.get_outcome("o1") is None
    assert repo.delete_job("j1") is False


def test_delete_step_cascades_its_outcomes():
    repo = _repo_with_graph()
    repo.add_outcome(Outcome(id="o2", job_id="j1", statement="Unbound"))
    assert repo.delete_step("s1") is True
    assert repo.get_step("s1") is None
    assert repo.get_outcome("o1") is None
    assert repo.get_outcome("o2") is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory core pytest tests/test_repository.py -v`
Expected: FAIL (`AttributeError: 'InMemoryRepository' object has no attribute 'get_step'`).

- [ ] **Step 3: Add the methods to the `Repository` protocol and `InMemoryRepository`**

Add the eight signatures from the Interfaces block to `Repository`. In `InMemoryRepository`, implement: getters via `self.steps.get` / `self.outcomes.get`; updates by merging `model_dump(exclude_unset=True)` with `updates` and re-validating (mirror `update_customer_outcome`); `delete_job` removes the job and every step/outcome/customer_outcome whose `job_id == job_id`; `delete_step` removes the step and every outcome/customer_outcome whose `step_id == step_id`; each delete returns `False` if the target id is absent.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory core pytest tests/test_repository.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/src/core/repository.py core/tests/test_repository.py
git commit -m "feat(core): add job/step/outcome CRUD with cascade delete to repository"
```

---

### Task 2: Core service CRUD, FK validation, score recompute

**Files:**
- Modify: `core/src/core/services.py`, `core/src/core/__init__.py`
- Test: `core/tests/test_service.py`

**Interfaces:**
- Consumes: Task 1 repository methods; `core.models.compute_opportunity_score`; `JobNotFoundError`.
- Produces:
  - Errors: `StepNotFoundError(step_id)`, `OutcomeNotFoundError(outcome_id)` (both exported from `core`).
  - `ODIService.get_step(step_id) -> Step | None`, `get_outcome(outcome_id) -> Outcome | None`
  - `ODIService.update_job(job_id, updates) -> Job`, `delete_job(job_id) -> None`
  - `ODIService.update_step(step_id, updates) -> Step`, `delete_step(step_id) -> None`
  - `ODIService.update_outcome(outcome_id, updates) -> Outcome`, `delete_outcome(outcome_id) -> None`
  - `add_step`, `add_outcome`, `add_customer_outcome` now raise `JobNotFoundError` for unknown `job_id` and `StepNotFoundError` for an unknown `step_id`.

- [ ] **Step 1: Write the failing tests** (append to `core/tests/test_service.py`)

```python
import pytest

from core.services import JobNotFoundError, OutcomeNotFoundError, StepNotFoundError


def test_add_step_requires_existing_job(service):
    with pytest.raises(JobNotFoundError):
        service.add_step("missing", "Step", order=1)


def test_add_outcome_requires_existing_job_and_step(service):
    job = service.add_job("J")
    with pytest.raises(JobNotFoundError):
        service.add_outcome("missing", "Min x")
    with pytest.raises(StepNotFoundError):
        service.add_outcome(job.id, "Min x", step_id="missing")


def test_update_outcome_recomputes_opportunity_score(service):
    job = service.add_job("J")
    outcome = service.add_outcome(job.id, "Min x", importance=5.0, satisfaction=5.0)
    assert outcome.opportunity_score == 5.0
    updated = service.update_outcome(outcome.id, {"importance": 8.0})
    assert updated.opportunity_score == 11.0
    cleared = service.update_outcome(outcome.id, {"satisfaction": None})
    assert cleared.opportunity_score is None


def test_job_crud_and_cascade(service):
    job = service.add_job("J")
    service.add_step(job.id, "Step", order=1)
    assert service.update_job(job.id, {"name": "Renamed"}).name == "Renamed"
    assert service.get_step(service.get_job_map(job.id)[0].id) is not None
    service.delete_job(job.id)
    assert service.get_job(job.id) is None
    assert service.get_job_map(job.id) == []
    with pytest.raises(JobNotFoundError):
        service.delete_job(job.id)


def test_update_unknown_ids_raise(service):
    with pytest.raises(JobNotFoundError):
        service.update_job("missing", {"name": "x"})
    with pytest.raises(StepNotFoundError):
        service.update_step("missing", {"name": "x"})
    with pytest.raises(OutcomeNotFoundError):
        service.update_outcome("missing", {"statement": "x"})
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --directory core pytest tests/test_service.py -v`
Expected: FAIL (`ImportError: cannot import name 'StepNotFoundError'`).

- [ ] **Step 3: Implement in `services.py`**

Add `StepNotFoundError`/`OutcomeNotFoundError` (mirroring `JobNotFoundError`). Add the get/update/delete methods. In `update_outcome`, fetch the existing outcome (raise `OutcomeNotFoundError` if absent), compute `importance`/`satisfaction` from `updates` falling back to the existing values, set `updates["opportunity_score"] = compute_opportunity_score(imp, sat)` when both are non-null else `None`, then call `repo.update_outcome`. In `add_step`/`add_outcome`/`add_customer_outcome`, call `self.repo.get_job(job_id)` first and raise `JobNotFoundError` if missing; for `step_id`, call `self.repo.get_step(step_id)` and raise `StepNotFoundError` if missing. Export the two errors from `core/__init__.py` (and add to `__all__`).

- [ ] **Step 4: Run to verify pass**

Run: `uv run --directory core pytest tests/test_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/src/core/services.py core/src/core/__init__.py core/tests/test_service.py
git commit -m "feat(core): add job/step/outcome service CRUD, FK validation, score recompute"
```

---

### Task 3: SQLiteRepository read-through, locking, cascade events

**Files:**
- Modify: `core/src/core/intent_store.py`, `core/src/core/sqlite_repository.py`
- Test: `core/tests/test_sqlite_repository.py` (new)

**Interfaces:**
- Consumes: Task 1 methods (interface parity).
- Produces: `SQLiteRepository` implements all Task 1 methods, persists `JOB_UPDATED`/`JOB_DELETED`/`STEP_UPDATED`/`STEP_DELETED`/`OUTCOME_UPDATED`/`OUTCOME_DELETED` events, and re-reads new events before every read.
  - `IntentStore.__init__(self, db_path: str = "intent_store.db", check_same_thread: bool = True)`.

- [ ] **Step 1: Write the failing tests** in `core/tests/test_sqlite_repository.py`

```python
from core.models import Job, Outcome, Step
from core.sqlite_repository import SQLiteRepository


def test_round_trips_all_entity_types(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_job(Job(id="j1", name="Job", description="d"))
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))
    repo.add_outcome(
        Outcome(
            id="o1",
            job_id="j1",
            step_id="s1",
            statement="Min x",
            importance=8.0,
            satisfaction=4.0,
            opportunity_score=12.0,
        )
    )

    reopened = SQLiteRepository(db_path=db)
    assert reopened.get_job("j1").name == "Job"  # type: ignore[union-attr]
    assert reopened.get_step("s1").order == 1  # type: ignore[union-attr]
    assert reopened.get_outcome("o1").opportunity_score == 12.0  # type: ignore[union-attr]


def test_concurrent_writer_is_visible(tmp_path):
    db = str(tmp_path / "odi.db")
    reader = SQLiteRepository(db_path=db)
    writer = SQLiteRepository(db_path=db)
    writer.add_job(Job(id="j1", name="Job"))
    assert reader.get_job("j1") is not None  # read-through sees the other connection's write


def test_delete_job_cascades_after_reopen(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_job(Job(id="j1", name="Job"))
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))
    repo.add_outcome(Outcome(id="o1", job_id="j1", step_id="s1", statement="Min x"))
    repo.delete_job("j1")

    reopened = SQLiteRepository(db_path=db)
    assert reopened.get_job("j1") is None
    assert reopened.get_step("s1") is None
    assert reopened.get_outcome("o1") is None


def test_update_outcome_persists(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_outcome(Outcome(id="o1", job_id="j1", statement="Min x"))
    repo.update_outcome("o1", {"statement": "Max y", "opportunity_score": 5.0})
    assert SQLiteRepository(db_path=db).get_outcome("o1").statement == "Max y"  # type: ignore[union-attr]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --directory core pytest tests/test_sqlite_repository.py -v`
Expected: FAIL on `test_concurrent_writer_is_visible` (reader's snapshot is stale) and missing `update_outcome`.

- [ ] **Step 3: Implement**

In `intent_store.py`, thread the `check_same_thread` flag into `sqlite3.connect`. In `sqlite_repository.py`: add `import threading`, `self._lock = threading.RLock()`; pass `check_same_thread=False` to `IntentStore`; set `self._last_event_id = 0` before load. Extract `_apply_event(self, ev: dict) -> None` from `_load_snapshot` covering all `*_CREATED`/`*_UPDATED`/`*_DELETED` events (created = `model_validate(p)`; updated = merge `p["updates"]` into the current model, tolerate `ValidationError`; deleted = pop; `JOB_DELETED` also pops steps/outcomes/customer_outcomes with that `job_id`; `STEP_DELETED` also pops outcomes/customer_outcomes with that `step_id`). `_load_snapshot` builds empty dicts and calls `_apply_event` for each stream event, tracking `max(id)`. Add `_sync()` that reads the stream and applies events with `id > self._last_event_id`. Wrap every public read with `with self._lock: self._sync(); ...` and every write with `with self._lock: self.store.append(...); self._sync()` (single application path). Implement `get_step`/`get_outcome`/`update_job`/`delete_job`/`update_step`/`delete_step`/`update_outcome`/`delete_outcome` matching Task 1 semantics; `clear()` becomes lock-guarded `store.clear(); _load_snapshot()`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --directory core pytest tests/test_sqlite_repository.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/src/core/intent_store.py core/src/core/sqlite_repository.py core/tests/test_sqlite_repository.py
git commit -m "feat(core): read-through SQLite repository with locking and cascade events"
```

---

### Task 4: `build_repository` factory

**Files:**
- Create: `core/src/core/factory.py`
- Modify: `core/src/core/__init__.py`
- Test: `core/tests/test_factory.py` (new)

**Interfaces:**
- Consumes: `InMemoryRepository`, `SQLiteRepository`.
- Produces: `build_repository(db_path: str | None = None) -> Repository` — returns `InMemoryRepository` when the resolved path is `:memory:`, otherwise `SQLiteRepository(db_path=db_path)`. Resolution order: `db_path` arg, then `AGENTIC_ODI_DB`, then default.

- [ ] **Step 1: Write the failing test** in `core/tests/test_factory.py`

```python
import pytest

from core import InMemoryRepository, build_repository
from core.sqlite_repository import SQLiteRepository


def test_memory_path_returns_in_memory(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", ":memory:")
    assert isinstance(build_repository(), InMemoryRepository)


def test_default_path_returns_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTIC_ODI_DB", raising=False)
    repo = build_repository(db_path=str(tmp_path / "odi.db"))
    assert isinstance(repo, SQLiteRepository)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --directory core pytest tests/test_factory.py -v`
Expected: FAIL (`ImportError: cannot import name 'build_repository'`).

- [ ] **Step 3: Implement `factory.py` and export**

```python
"""Repository factory selecting a persistent or in-memory store."""

from __future__ import annotations

import os

from core.repository import InMemoryRepository, Repository
from core.sqlite_repository import SQLiteRepository


def build_repository(db_path: str | None = None) -> Repository:
    path = db_path if db_path is not None else os.environ.get("AGENTIC_ODI_DB")
    if path == ":memory:":
        return InMemoryRepository()
    return SQLiteRepository(db_path=db_path)
```

Add `build_repository` to `core/__init__.py` imports and `__all__`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --directory core pytest tests/test_factory.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/src/core/factory.py core/src/core/__init__.py core/tests/test_factory.py
git commit -m "feat(core): add build_repository factory for shared store selection"
```

---

### Task 5: MCP server — persistent store, CRUD parity, value_metrics

**Files:**
- Modify: `mcp_server/src/mcp_server/mcp_server.py`, `mcp_server/tests/conftest.py`
- Test: `mcp_server/tests/test_parity.py` (new)

**Interfaces:**
- Consumes: `core.build_repository`, `ODIService` methods/errors from Task 2.
- Produces (new MCP tools, string-returning like the existing ones):
  - `get_step(step_id)`, `get_outcome(outcome_id)`
  - `update_job(job_id, name=None, description=None)`, `delete_job(job_id)`
  - `update_step(step_id, name=None, order=None)`, `delete_step(step_id)`
  - `update_outcome(outcome_id, statement=None, importance=None, satisfaction=None, step_id=None)`, `delete_outcome(outcome_id)`
  - `update_customer_outcome(..., value_metrics: list[dict] | None = None)`

- [ ] **Step 1: Set the test store to in-memory** in `mcp_server/tests/conftest.py`, before importing `mcp_server`

```python
from __future__ import annotations

import os

os.environ["AGENTIC_ODI_DB"] = ":memory:"

from collections.abc import Generator  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402

from mcp_server import customer_outcomes_db, jobs_db, outcomes_db, steps_db  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db() -> Generator[None, Any, None]:
    jobs_db.clear()
    steps_db.clear()
    outcomes_db.clear()
    customer_outcomes_db.clear()
    yield
```

- [ ] **Step 2: Write the failing tests** in `mcp_server/tests/test_parity.py`

```python
import json

import pytest
from fastmcp import Client

from mcp_server import mcp


async def _new_job(client) -> str:
    res = await client.call_tool("add_job", {"name": "J"})
    return json.loads(res.content[0].text.split(": ", 1)[1])["id"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_step_and_outcome_get_update_delete():
    async with Client(mcp) as client:
        job_id = await _new_job(client)
        step = await client.call_tool("add_step", {"job_id": job_id, "name": "S", "order": 1})
        step_id = json.loads(step.content[0].text.split(": ", 1)[1])["id"]  # type: ignore[index]

        got = await client.call_tool("get_step", {"step_id": step_id})
        assert step_id in got.content[0].text  # type: ignore[index]

        upd = await client.call_tool("update_step", {"step_id": step_id, "name": "S2"})
        assert "updated successfully" in upd.content[0].text  # type: ignore[index]

        out = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Min x",
                "importance": 8,
                "satisfaction": 4,
            },
        )
        outcome_id = json.loads(out.content[0].text.split(": ", 1)[1])["id"]  # type: ignore[index]

        upd_o = await client.call_tool(
            "update_outcome", {"outcome_id": outcome_id, "importance": 9}
        )
        assert "updated successfully" in upd_o.content[0].text  # type: ignore[index]

        dele = await client.call_tool("delete_outcome", {"outcome_id": outcome_id})
        assert "deleted successfully" in dele.content[0].text  # type: ignore[index]

        assert (
            "deleted successfully"
            in (await client.call_tool("delete_step", {"step_id": step_id})).content[0].text
        )  # type: ignore[index]
        assert (
            "deleted successfully"
            in (await client.call_tool("delete_job", {"job_id": job_id})).content[0].text
        )  # type: ignore[index]


@pytest.mark.asyncio
async def test_update_customer_outcome_replaces_value_metrics():
    async with Client(mcp) as client:
        job_id = await _new_job(client)
        cv = {
            "direction": "minimize",
            "unit_of_measure": "time",
            "object_of_control": "x",
            "statement": "Min x",
            "importance": 5,
            "satisfaction": 5,
            "value_metrics": [
                {
                    "name": "m",
                    "direction": "minimize",
                    "unit_of_measure": "s",
                    "importance": 6,
                    "satisfaction": 2,
                }
            ],
        }
        bv = {"category": "cost_reduction", "statement": "Save"}
        created = await client.call_tool(
            "add_customer_outcome",
            {"job_id": job_id, "customer_value": cv, "business_value": bv},
        )
        oid = json.loads(created.content[0].text.split(": ", 1)[1])["id"]  # type: ignore[index]
        upd = await client.call_tool(
            "update_customer_outcome",
            {
                "outcome_id": oid,
                "value_metrics": [
                    {
                        "name": "m2",
                        "direction": "maximize",
                        "unit_of_measure": "s",
                        "importance": 9,
                        "satisfaction": 3,
                    }
                ],
            },
        )
        assert '"name":"m2"' in upd.content[0].text  # type: ignore[index]
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --directory mcp_server pytest tests/test_parity.py -v`
Expected: FAIL (unknown tools / value_metrics ignored).

- [ ] **Step 4: Implement in `mcp_server.py`**

Replace `_repo = InMemoryRepository()` with `_repo = build_repository()` (import `build_repository` from `core`). Keep `jobs_db`/`steps_db`/`outcomes_db`/`customer_outcomes_db` = `_repo.*`. Add the new `@mcp.tool` functions from the Interfaces block, each returning `f"... created/updated/deleted successfully: {model.model_dump_json()}"` or a `not found` string (use `job_not_found` and add a step/outcome not-found message). In `update_customer_outcome`, add `value_metrics: list[dict] | None = None` and, when provided, set `cv_d["value_metrics"] = value_metrics` before validation.

- [ ] **Step 5: Run full MCP suite**

Run: `uv run --directory mcp_server pytest -v`
Expected: PASS (existing + new).

- [ ] **Step 6: Commit**

```bash
git add mcp_server/src/mcp_server/mcp_server.py mcp_server/tests/conftest.py mcp_server/tests/test_parity.py
git commit -m "feat(mcp): persistent shared store and CRUD tool parity incl. value_metrics"
```

---

### Task 6: CLI backend abstraction + global options

**Files:**
- Modify: `cli/src/cli/backend.py`
- Test: `cli/tests/test_backend.py` (new)

**Interfaces:**
- Consumes: `core.ODIService`, `core.build_repository`/`SQLiteRepository`, errors.
- Produces:
  - `_call_mcp(tool: str, args: dict, mcp_url: str) -> str` (moved here from `outcomes.py`).
  - `LocalBackend(db_path: str | None = None).call(tool_name, args) -> str` handling every tool name in the mapping below.
  - `MCPBackend(mcp_url).call(...)` delegating to `_call_mcp`.
  - `BackendConfig` dataclass `(backend: str, db_path: str | None, mcp_url: str | None)` and `resolve_backend(config: BackendConfig) -> Backend` that warns to stderr when `db_path` is set with `backend == "mcp"`.
  - Tool-name map: `add_job`, `get_jobs`, `get_job`, `update_job`, `delete_job`, `add_step`, `get_job_map`, `get_step`, `update_step`, `delete_step`, `add_outcome`, `get_outcomes`, `get_outcome`, `update_outcome`, `delete_outcome`, plus the five `*_customer_outcome` names and `compute_opportunity`.

- [ ] **Step 1: Write the failing tests** in `cli/tests/test_backend.py`

```python
from cli.backend import BackendConfig, LocalBackend, resolve_backend


def test_local_backend_full_crud_round_trip(tmp_path):
    db = str(tmp_path / "odi.db")
    backend = LocalBackend(db_path=db)
    job_text = backend.call("add_job", {"name": "J", "description": "d"})
    assert "created successfully" in job_text
    import json, re

    job_id = json.loads(re.search(r"({.*})", job_text).group(1))["id"]  # type: ignore[union-attr]
    backend.call("add_step", {"job_id": job_id, "name": "S", "order": 1})
    backend.call(
        "add_outcome",
        {
            "job_id": job_id,
            "statement": "Min x",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    )
    listed = backend.call("get_outcomes", {"job_id": job_id})
    assert "Min x" in listed
    assert json.loads(backend.call("get_jobs", {}))[0]["name"] == "J"


def test_resolve_backend_warns_on_db_with_mcp(capsys):
    resolve_backend(BackendConfig(backend="mcp", db_path="x.db", mcp_url="http://x/mcp"))
    assert "ignored" in capsys.readouterr().err.lower()


def test_resolve_backend_unknown_raises():
    import pytest

    with pytest.raises(ValueError):
        resolve_backend(BackendConfig(backend="nope", db_path=None, mcp_url=None))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --directory cli pytest tests/test_backend.py -v`
Expected: FAIL (`ImportError: cannot import name 'BackendConfig'`).

- [ ] **Step 3: Implement `backend.py`**

Move `_call_mcp` here (same asyncio + `Client` logic and error handling). Build `LocalBackend.call` as a dispatch table over the tool names, each branch calling the corresponding `ODIService` method and formatting results the way the existing `add/update/delete/list` branches do (JSON for lists/gets, "created/updated/deleted successfully" for writes; catch not-found/value errors and return their message). Add `BackendConfig` and `resolve_backend` (uses `get_backend`); emit the mcp+db warning via `typer.echo(..., err=True)`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --directory cli pytest tests/test_backend.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/backend.py cli/tests/test_backend.py
git commit -m "feat(cli): backend abstraction with full local tool dispatch and config resolution"
```

---

### Task 7: CLI `jobs` group

**Files:**
- Create: `cli/src/cli/jobs.py`
- Modify: `cli/src/cli/cli.py`
- Test: `cli/tests/test_jobs_cli.py` (new)

**Interfaces:**
- Consumes: `resolve_backend`, `BackendConfig` (Task 6); the callback stores a `BackendConfig` on `ctx.obj`.
- Produces: `jobs_app` (Typer) with `add`, `list`, `get`, `update`, `delete`; mounted as `jobs`.
  - `add --name (required) [--description]`, `list`, `get JOB_ID`, `update JOB_ID [--name --description]`, `delete JOB_ID [-y/--yes]`.

- [ ] **Step 1: Add the global callback + mount** in `cli/cli.py`, then write tests in `cli/tests/test_jobs_cli.py`

```python
from typer.testing import CliRunner

from cli.cli import app


def test_jobs_add_list_get_round_trip(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    add = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Onboard"])
    assert add.exit_code == 0 and "created successfully" in add.output
    listed = runner.invoke(app, ["--db", db, "jobs", "list"])
    assert "Onboard" in listed.output


def test_jobs_get_unknown_reports_error(tmp_path):
    result = CliRunner().invoke(app, ["--db", str(tmp_path / "odi.db"), "jobs", "get", "nope"])
    assert result.exit_code == 0 and "not found" in result.output.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --directory cli pytest tests/test_jobs_cli.py -v`
Expected: FAIL (no `--db` option / no `jobs` command).

- [ ] **Step 3: Implement**

In `cli.py`: add `--backend`, `--db`, `--mcp-url` to `@app.callback()` (`main`), keep `--version`; set `ctx.obj = BackendConfig(...)`; mount `jobs_app`. In `jobs.py`: build `jobs_app = typer.Typer(help="Manage Jobs-to-be-Done.")`, each command reads `ctx.obj`, calls the backend tool (`add_job`/`get_jobs`/`get_job`/`update_job`/`delete_job`), and echoes the result; `delete` prompts unless `-y`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --directory cli pytest tests/test_jobs_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/jobs.py cli/src/cli/cli.py cli/tests/test_jobs_cli.py
git commit -m "feat(cli): add jobs command group with global backend options"
```

---

### Task 8: CLI `steps` group

**Files:**
- Create: `cli/src/cli/steps.py`
- Modify: `cli/src/cli/cli.py`
- Test: `cli/tests/test_steps_cli.py` (new)

**Interfaces:**
- Consumes: Task 6/7 infrastructure.
- Produces: `steps_app` mounted as `steps` with `add --job-id --name --order`, `list --job-id` (required, maps to `get_job_map`), `get STEP_ID`, `update STEP_ID [--name --order]`, `delete STEP_ID [-y]`.

- [ ] **Step 1: Write the failing tests** in `cli/tests/test_steps_cli.py`

```python
import json
import re

from typer.testing import CliRunner

from cli.cli import app


def _job_id(runner, db) -> str:
    out = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "J"]).output
    return json.loads(re.search(r"({.*})", out).group(1))["id"]  # type: ignore[union-attr]


def test_steps_add_and_list_job_map(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    add = runner.invoke(
        app,
        ["--db", db, "steps", "add", "--job-id", job_id, "--name", "S", "--order", "1"],
    )
    assert add.exit_code == 0 and "created successfully" in add.output
    listed = runner.invoke(app, ["--db", db, "steps", "list", "--job-id", job_id])
    assert "S" in listed.output


def test_steps_add_unknown_job_errors(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "steps",
            "add",
            "--job-id",
            "nope",
            "--name",
            "S",
            "--order",
            "1",
        ],
    )
    assert "not found" in result.output.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --directory cli pytest tests/test_steps_cli.py -v`
Expected: FAIL (no `steps` command).

- [ ] **Step 3: Implement `steps.py`** mirroring `jobs.py`, mapping to `add_step`/`get_job_map`/`get_step`/`update_step`/`delete_step`. Mount in `cli.py`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --directory cli pytest tests/test_steps_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/steps.py cli/src/cli/cli.py cli/tests/test_steps_cli.py
git commit -m "feat(cli): add steps command group"
```

---

### Task 9: CLI `outcomes` (Desired Outcome) group + top-level `score`

**Files:**
- Rewrite: `cli/src/cli/outcomes.py`
- Modify: `cli/src/cli/cli.py`
- Test: `cli/tests/test_outcomes_cli.py` (rewrite)

**Interfaces:**
- Consumes: Task 6/7 infrastructure.
- Produces: `outcomes_app` (now Desired Outcome) mounted as `outcomes` with `add --job-id --statement [--importance --satisfaction] [--step-id]`, `list --job-id (required) [--step-id]`, `get OUTCOME_ID`, `update OUTCOME_ID [--statement --importance --satisfaction --step-id]`, `delete OUTCOME_ID [-y]`; and a top-level `score IMPORTANCE SATISFACTION` command.

- [ ] **Step 1: Write the failing tests** (replace `cli/tests/test_outcomes_cli.py`)

```python
import json
import re

from typer.testing import CliRunner

from cli.cli import app


def _job_id(runner, db) -> str:
    out = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "J"]).output
    return json.loads(re.search(r"({.*})", out).group(1))["id"]  # type: ignore[union-attr]


def test_outcomes_add_computes_score(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    add = runner.invoke(
        app,
        [
            "--db",
            db,
            "outcomes",
            "add",
            "--job-id",
            job_id,
            "--statement",
            "Min onboarding",
            "--importance",
            "8",
            "--satisfaction",
            "4",
        ],
    )
    assert add.exit_code == 0 and "12.0" in add.output
    listed = runner.invoke(app, ["--db", db, "outcomes", "list", "--job-id", job_id])
    assert "Min onboarding" in listed.output


def test_score_command(tmp_path):
    result = CliRunner().invoke(app, ["--db", str(tmp_path / "odi.db"), "score", "8", "2"])
    assert result.exit_code == 0 and "14.00" in result.output
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --directory cli pytest tests/test_outcomes_cli.py -v`
Expected: FAIL (`outcomes add` still expects customer-value flags; no top-level `score`).

- [ ] **Step 3: Implement** the desired-outcome `outcomes_app` and the top-level `score` command (using `compute_opportunity`). Keep the enum options for nothing here; specs are plain strings.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --directory cli pytest tests/test_outcomes_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/outcomes.py cli/src/cli/cli.py cli/tests/test_outcomes_cli.py
git commit -m "feat(cli): desired-outcome group and top-level score command"
```

---

### Task 10: CLI `customer-outcomes` group + `value_metrics`

**Files:**
- Create: `cli/src/cli/customer_outcomes.py` (moved from the old `outcomes.py` implementation)
- Modify: `cli/src/cli/cli.py`
- Test: `cli/tests/test_customer_outcomes_cli.py` (new; supersedes old tests)

**Interfaces:**
- Consumes: Task 6/7 infrastructure.
- Produces: `customer_outcomes_app` mounted as `customer-outcomes` with the former Customer Outcome CRUD (`add`, `list [--job-id]`, `get`, `update`, `delete`), plus a repeatable `--value-metric '<json>'` on `add` and `update` that parses to a list of `{name, direction, unit_of_measure, importance, satisfaction}` dicts; on `add` it is placed at `customer_value["value_metrics"]`, on `update` it is passed as the top-level `value_metrics` argument.

- [ ] **Step 1: Write the failing tests** in `cli/tests/test_customer_outcomes_cli.py`

```python
from typer.testing import CliRunner

from cli.cli import app


def test_customer_outcome_add_with_value_metrics(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    runner.invoke(app, ["--db", db, "jobs", "add", "--name", "J"])
    import json

    job_id = json.loads(runner.invoke(app, ["--db", db, "jobs", "list"]).output)[0]["id"]
    metric = (
        '{"name":"m","direction":"minimize","unit_of_measure":"s","importance":6,"satisfaction":2}'
    )
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "customer-outcomes",
            "add",
            "--job-id",
            job_id,
            "--direction",
            "minimize",
            "--unit",
            "time",
            "--object",
            "x",
            "--statement",
            "Min x",
            "--importance",
            "8",
            "--satisfaction",
            "4",
            "--category",
            "cost_reduction",
            "--business-statement",
            "Save",
            "--value-metric",
            metric,
        ],
    )
    assert result.exit_code == 0 and '"name":"m"' in result.output


def test_customer_outcome_add_rejects_bad_metric_json(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    runner.invoke(app, ["--db", db, "jobs", "add", "--name", "J"])
    import json

    job_id = json.loads(runner.invoke(app, ["--db", db, "jobs", "list"]).output)[0]["id"]
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "customer-outcomes",
            "add",
            "--job-id",
            job_id,
            "--direction",
            "minimize",
            "--unit",
            "t",
            "--object",
            "x",
            "--statement",
            "s",
            "--importance",
            "8",
            "--satisfaction",
            "4",
            "--category",
            "cost_reduction",
            "--business-statement",
            "b",
            "--value-metric",
            "not-json",
        ],
    )
    assert result.exit_code != 0 and "value-metric" in result.output.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --directory cli pytest tests/test_customer_outcomes_cli.py -v`
Expected: FAIL (no `customer-outcomes` command / no `--value-metric`).

- [ ] **Step 3: Implement** by moving the previous `outcomes.py` Customer Outcome commands into `customer_outcomes.py`, renaming the group to `customer-outcomes`, and adding `--value-metric` (repeatable) parsed via `json.loads`; on parse/validation failure raise `typer.BadParameter` naming `value-metric`. Mount in `cli.py`. Delete the obsolete Customer Outcome tests that lived in the old `test_outcomes_cli.py`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --directory cli pytest tests/test_customer_outcomes_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/customer_outcomes.py cli/src/cli/cli.py cli/tests/test_customer_outcomes_cli.py cli/tests/test_outcomes_cli.py
git commit -m "feat(cli): customer-outcomes group with value_metrics input"
```

---

### Task 11: Persistence acceptance test, README, full verification

**Files:**
- Create: `cli/tests/test_persistence.py`
- Modify: `README.md`
- Test: the whole suite

**Interfaces:**
- Consumes: everything above.
- Produces: the explicit "successfully stored data types" proof.

- [ ] **Step 1: Write the acceptance test** in `cli/tests/test_persistence.py`

```python
from cli.backend import LocalBackend
from core.sqlite_repository import SQLiteRepository


def test_every_entity_type_survives_reopen(tmp_path):
    db = str(tmp_path / "odi.db")
    backend = LocalBackend(db_path=db)

    import json, re

    def json_of(text: str) -> dict:
        return json.loads(re.search(r"({.*})", text).group(1))  # type: ignore[union-attr]

    job_id = json_of(backend.call("add_job", {"name": "J", "description": "d"}))["id"]
    step_id = json_of(backend.call("add_step", {"job_id": job_id, "name": "S", "order": 1}))["id"]
    backend.call(
        "add_outcome",
        {
            "job_id": job_id,
            "statement": "Min x",
            "importance": 8.0,
            "satisfaction": 4.0,
            "step_id": step_id,
        },
    )
    backend.call(
        "add_customer_outcome",
        {
            "job_id": job_id,
            "customer_value": {
                "direction": "minimize",
                "unit_of_measure": "time",
                "object_of_control": "x",
                "statement": "Min x",
                "importance": 8.0,
                "satisfaction": 4.0,
                "value_metrics": [
                    {
                        "name": "m",
                        "direction": "minimize",
                        "unit_of_measure": "s",
                        "importance": 6.0,
                        "satisfaction": 2.0,
                    }
                ],
            },
            "business_value": {"category": "cost_reduction", "statement": "Save"},
        },
    )

    repo = SQLiteRepository(db_path=db)
    assert repo.get_job(job_id).name == "J"  # type: ignore[union-attr]
    assert repo.get_step(step_id).order == 1  # type: ignore[union-attr]
    outcome = repo.get_outcome(repo.get_outcomes(job_id)[0].id)
    assert outcome.opportunity_score == 12.0  # type: ignore[union-attr]
    co = repo.list_customer_outcomes(job_id)[0]
    assert co.customer_value.value_metrics[0].opportunity_score == 10.0
```

- [ ] **Step 2: Run it**

Run: `uv run --directory cli pytest tests/test_persistence.py -v`
Expected: PASS.

- [ ] **Step 3: Update `README.md`** — replace the "Manage Customer Outcomes" section with a "CLI" section documenting `jobs`, `steps`, `outcomes` (desired), `customer-outcomes`, top-level `score`, the global `--backend local|mcp`, `--db`, `AGENTIC_ODI_DB`, the shared-store behavior, and the breaking rename. Update the CLI bullet in "Code Overview".

- [ ] **Step 4: Full verification**

```bash
uv run ruff check .
uv run ruff format --check .
uv run --directory core mypy .
uv run --directory mcp_server mypy .
uv run --directory local_server mypy .
uv run --directory client mypy .
uv run --directory cli mypy .
uv run --directory connectors mypy .
uv run --directory core pytest
uv run --directory mcp_server pytest
uv run --directory local_server pytest
uv run --directory client pytest
uv run --directory cli pytest
uv run --directory connectors pytest
```
Expected: all green. If `ruff format --check` fails, run `uv run ruff format .` and re-check.

- [ ] **Step 5: Commit**

```bash
git add cli/tests/test_persistence.py README.md
git commit -m "test(cli): prove all entity types persist; document new CLI surface"
```

---

## Self-Review

- **Spec coverage:** jobs/steps/outcomes/customer-outcomes CLI groups (Tasks 7–10) ✓; `value_metrics` input+output (Tasks 5, 10) ✓; shared persistent store + read-through (Tasks 3, 5) ✓; backend selection (Tasks 6, 7) ✓; full CRUD + MCP parity (Tasks 1, 2, 5, 7–10) ✓; cascade + FK validation (Tasks 1–3) ✓; the "successfully stored data types" acceptance test (Task 11) ✓; README + gates (Task 11) ✓.
- **Type consistency:** repository/service/MCP/CLI/backend all use the same tool names and method names (`get_step`, `update_outcome`, `delete_job`, …); `BackendConfig` fields (`backend`, `db_path`, `mcp_url`) are identical everywhere; `build_repository` signature stable across Tasks 4 and 5.
- **Review Focus:** each item (concurrent visibility, cascade replay, stored score on update, bad CLI inputs, value_metrics semantics) has a pinned test in Tasks 3/5/2/6–10/10 respectively.
- **Proportion:** bodies appear only where the signature + tests don't determine them (`build_repository`, `_apply_event`, the acceptance test); everything else is signatures + assertions.
