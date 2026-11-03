# ALH-222 · CSV Outcome Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import desired Outcomes from a CSV through `odi desired-outcomes import` and `POST /api/outcomes/import`, with one shared parser, one shared row-level report, and a preview that writes nothing.

**Architecture:** `packages/core` gains `outcome_import.py` (methodology layer) holding `parse_outcome_table` and `import_outcomes`. The loop talks to an `ImportTarget` protocol — three batched reads and two writes — so the service, the CLI's `run_tool`, and the Studio's `call_mcp_tool` each satisfy it without a new MCP tool. Both doors therefore assemble the same `ImportReport` from the same fixture bytes.

**Tech Stack:** Python 3.10+ (stdlib `csv`), Typer, FastAPI + `python-multipart`, pytest, React/TS artifacts regenerated only.

**Spec:** `docs/superpowers/specs/2026-11-03-alh-222-csv-outcome-import-design.md`

## Global Constraints

- Statement validity is decided by `evaluate_outcome_statement`; nothing repairs a statement and nothing bypasses that check.
- Score bounds are 1.0–10.0 per field. A blank score cell stays `None`; it is never coerced to `0`.
- A row with `importance` or `satisfaction` and no supplied claim check is written with `manual_claim_check()`; a row with neither is written with none.
- Theme matching is exact and case-sensitive against the target job's themes plus workspace themes (`job_id is None`). No creation, no fuzzy match, no silent pick.
- `line` in every report entry is the physical file line from `csv.reader.line_num`, header on line 1.
- The MCP server's tool surface does not change: no new `ToolName`, no `TOOL_SPECS` edit, no `mcp_server.py` edit.
- `uv run mypy apps brand packages` (CI, `.github/workflows/ci.yml:73`), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`, `uv run python scripts/doc_check.py` must pass at the end of every task.
- Keep `README.md` and `docs/cli.md` current in the same task that changes behavior (`website/tests/test_generated.py::test_the_cli_reference_mentions_every_registered_command` enforces the reference).

## Review Focus

Inputs no task's tests would otherwise exercise, and what a person is owed when they arrive:

1. **A file whose scores are all blank.** Expect: every row creates an unscored outcome; `importance=None`, not `0`, and no `opportunity_score`. Pinned in Task 1 and Task 2.
2. **A dead MCP server halfway through an upload.** Expect: the run stops, rows already written are listed as created, one `aborted` entry names the line — never 20 invented refusals. Pinned in Task 5.
3. **An unscored row through the CLI's default local backend.** Today this raises `KeyError` in `LocalBackend._add_outcome`. Expect: the row is created. Pinned in Task 3, which owns the bug.
4. **A file exported by this tool being imported back.** Expect: statements, scores and `step_id` round trip; `id` and `opportunity_score` arrive in `ignored_columns` rather than being silently obeyed. Pinned in Task 1.
5. **The same file through both doors.** Expect: byte-identical reports. Pinned in Task 7, the last task, because it is the criterion the whole design exists to satisfy.

---

## Task 1: The shared fixture and `parse_outcome_table`

**Files:**
- Create: `packages/core/src/agentic_odi_core/outcome_import.py`
- Create: `packages/core/tests/fixtures/outcomes_mixed_40.csv`
- Create: `packages/core/tests/test_outcome_import.py`
- Modify: `packages/core/src/agentic_odi_core/__init__.py` (re-export)
- Modify: `tests/test_architecture.py:213` (add `"outcome_import"` to the `methodology` tuple)
- Modify: `docs/architecture/README.md:131` (name the module in the methodology row)

**Interfaces:**
- Produces for Tasks 2–7:
  ```python
  @dataclass(frozen=True)
  class ImportRow:
      line: int
      statement: str
      importance: float | None = None
      satisfaction: float | None = None
      importance_n: float | None = None
      satisfaction_n: float | None = None
      theme: str | None = None
      stage: str | None = None
      step_id: str | None = None
      job_id: str | None = None
      problems: list[str] = field(default_factory=list)  # a cell that is not a number, phrased

  @dataclass
  class ParsedTable:
      rows: list[ImportRow]
      ignored_columns: dict[str, str]   # header -> why nothing was done with it
      problems: list[str]               # file-level; non-empty means rows == []

  def parse_outcome_table(source: str | bytes, fmt: str = "csv") -> ParsedTable
  ```
- Consumes: nothing outside the stdlib and `agentic_odi_core.errors`.

- [x] **Step 1: write the fixture file.** Generate it once with this snippet, commit the bytes, and never regenerate them — three suites assert against these exact line numbers:

  ```python
  from pathlib import Path

  UNITS = ["time", "number", "cost", "steps", "errors", "duration", "frequency", "rate",
           "attempts", "share"]  # every one is in evaluation._find_unit_of_measure
  ACTIONS = ["reconcile a supplier invoice", "close the month-end ledger",
             "approve a credit request", "match a payment to an invoice",
             "catch a duplicate charge", "hand off an accrual"]
  CONTEXTS = ["when the statement arrives late", "when invoices mismatch",
              "before the ledger closes", "when a credit is requested",
              "after close reveals an error", "when the vendor disputes a charge",
              "while approvals wait for proof", "when two systems disagree",
              "before payment terms expire", "when an accrual is estimated",
              "during a month-end handoff", "when the audit trail breaks"]

  rows = ["statement,importance,satisfaction,theme,stage"]
  for i in range(40):  # data rows -> file lines 2..41; (i%10, i%12) is unique under 60,
                       # so all 40 statements differ and no row is an in-file duplicate.
      theme = ("Onboarding" if i < 6 else "Retention" if i < 10 else
               "Urgent" if i < 12 else "")
      stage = "execute" if i in {2, 3} else ""
      rows.append(f"Minimize the {UNITS[i % 10]} to {ACTIONS[i % 6]} "
                  f"{CONTEXTS[i % 12]},{8 - i % 5},{2 + i % 4},{theme},{stage}")
  rows[8] = "Minimize the number of mismatches found after close when reconciling,11,3,Onboarding,"  # line 9
  rows[17] = "Make it faster,7,2,,execute"                                                          # line 18
  rows[26] = "Minimize the time to approve a credit when the customer asks,6,1,,collect"             # line 27
  Path("packages/core/tests/fixtures/outcomes_mixed_40.csv").write_text(
      "\n".join(rows) + "\n", encoding="utf-8")
  ```

  `rows[0]` is the header, so `rows[8]`, `rows[17]` and `rows[26]` are data indices 7, 16 and 25
  — file lines 9, 18 and 27. Seed every job that uses this fixture with exactly one `EXECUTE`
  step and themes `Onboarding` (job), `Urgent` (job) and `Urgent` (workspace-wide). Then:
  `Onboarding` files lines 2–7; `Retention` is unmatched on lines 8, 10 and 11; `Urgent` is
  ambiguous on lines 12 and 13; line 9 refuses on the bounds, line 18 on the statement, line 27
  on `Unknown stage: collect`; 37 created, 3 refused, no in-file duplicates and no warnings.

- [x] **Step 2: run the parser tests to make sure they fail.** `uv run pytest packages/core/tests/test_outcome_import.py -q` → `ModuleNotFoundError: agentic_odi_core.outcome_import`.

- [x] **Step 3: write the tests** in `packages/core/tests/test_outcome_import.py`, module docstring naming ALH-222, and the fixture read the way `evaluation.py:186` reads its fixture:

  ```python
  FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "outcomes_mixed_40.csv"
  ```

  - `test_parse_reads_the_statement_synonyms` — `need,x` and `outcome,x` headers each map to `statement`; a file with `outcome` and `need` (same meaning) parses; a **row** whose two statement cells differ carries `problems == ['statement is ambiguous: …']` naming both headers while its neighbour rows still parse (a whole file never dies for one row).
  - `test_parse_uses_physical_line_numbers` — the first data row is line 2, and the fixture's bad score row is reported at the line Step 1 pins.
  - `test_parse_leaves_a_blank_score_as_none` — `,` in an importance cell gives `importance is None`; a `0` in the cell gives `0.0` — the two are different rows.
  - `test_parse_reports_ignored_columns_with_a_reason` — `Notes` lands in `ignored_columns` as an
    unknown column; `id`, `opportunity_score`, `importance_n`, `satisfaction_n` land there too,
    each with the reason it could not be used.
  - `test_parse_accepts_text_and_bytes` — the same document through both types gives equal `rows`.
  - `test_parse_refuses_a_non_csv_format` — `parse_outcome_table(text, fmt="xlsx")` raises `UnsupportedFormatError` whose message names `csv` as the only format this increment reads.
  - `test_parse_of_an_empty_file_reports_one_problem_at_line_1` — no header, and the same for a header with no `statement`/`outcome`/`need`.
  - `test_the_fixture_parses_to_forty_rows_with_three_broken` — `len(rows) == 40`, and the three rows at the pinned lines are the ones carrying `importance == 11`, the malformed statement, and `stage == "collect"`.
  - `test_an_exported_file_round_trips` — build the header `id,job_id,step_id,statement,importance,satisfaction,opportunity_score` (the CLI's `EXPORT_FIELDS`) with one row; the statement, scores and `step_id` are read, `id` and `opportunity_score` are reported, and nothing in `ignored_columns` reached a row field.

- [x] **Step 4: implement `parse_outcome_table`** in `outcome_import.py`. Read with `csv.reader` over `io.StringIO(newline="")`; normalise each header once (`strip().lower()`); canonical column names are `statement importance satisfaction importance_n satisfaction_n theme stage step_id job_id id job_id opportunity_score`; statement column = the first of `statement`, `outcome`, `need` present, and if two of them carry different non-empty header *names* as columns, refuse at parse time. `UnsupportedFormatError(OdiError)` is defined in this module. Numeric cells: empty → `None`, unparseable → keep the raw string on the row field typed `float | None` and let Task 2 refuse it (store the unparsed text in `ImportRow` as a `problems: list[str]` field on the row — one per bad cell, phrased `importance must be a number, got "soon"`).
- [x] **Step 5: `uv run pytest packages/core/tests/test_outcome_import.py -q`** → pass.
- [x] **Step 6: add the re-exports** (`ImportRow`, `ParsedTable`, `parse_outcome_table`) to `agentic_odi_core/__init__.py` and its `__all__`, keeping import order ruff-clean.
- [x] **Step 7: register the module** in `tests/test_architecture.py::CORE_LAYERS["methodology"]` and in the methodology row of the layer table in `docs/architecture/README.md`, then `uv run pytest tests/test_architecture.py -q`.
- [x] **Step 8: full gates** (`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy apps brand packages`, `uv run pytest -q`).
- [x] **Step 9: commit** `feat(core): parse an outcome CSV into rows (ALH-222)`.

## Task 2: `import_outcomes` — one loop, one report

**Files:**
- Modify: `packages/core/src/agentic_odi_core/outcome_import.py`
- Modify: `packages/core/src/agentic_odi_core/__init__.py`
- Test: `packages/core/tests/test_outcome_import.py` (append)

**Interfaces:**
- Consumes: Task 1's `ImportRow`/`ParsedTable`; `ODIService.add_outcome`, `assign_theme`, `list_themes`, `get_job_map`, `get_outcomes`; `manual_claim_check`; `evaluate_outcome_statement`; `JobStage`.
- Produces for Tasks 4–7:
  ```python
  @runtime_checkable
  class ImportTarget(Protocol):
      def themes(self, job_id: str) -> list[Theme]: ...
      def steps(self, job_id: str) -> list[Step]: ...
      def existing_statements(self, job_id: str) -> list[str]: ...
      def add_outcome(self, job_id: str, row: ImportRow, claim_check: ClaimCheck | None,
                      step_id: str | None) -> str: ...
      def assign_theme(self, outcome_ids: list[str], theme_id: str) -> None: ...

  class ServiceImportTarget:            # wraps ODIService
      def __init__(self, service: ODIService) -> None: ...

  class ImportAbortedError(OdiError): ...  # transport failure, not a row failure

  @dataclass
  class ImportReport:
      job_id: str
      dry_run: bool
      created: list[dict[str, Any]]     # line, statement, importance, satisfaction, outcome_id
      refused: list[dict[str, Any]]     # line, statement, reason
      unmatched_themes: list[dict[str, Any]]   # name, lines
      ambiguous_themes: list[dict[str, Any]]   # name, candidate_ids, lines
      ignored_columns: dict[str, str]
      warnings: list[str]
      aborted: dict[str, Any] | None    # line, reason
      def as_dict(self) -> dict[str, Any]: ...   # same key order as BulkReport.as_dict

  def import_outcomes(table: ParsedTable, target: ImportTarget, *, job_id: str,
                      dry_run: bool = False) -> ImportReport
  ```

- [x] **Step 1: append the failing tests.** Each seeds through `InMemoryRepository` + `ODIService` (the idiom in `packages/core/tests/test_bulk.py`), creating the job, exactly one step with `stage=JobStage.EXECUTE`, and themes named `Onboarding` (job-scoped), `Urgent` (job-scoped) and `Urgent` (workspace-scoped).
  - `test_the_fixture_writes_thirty_seven_and_refuses_three` — report has `len(created) == 37`, `len(refused) == 3`, the refusals' lines are the pinned three, the `importance == 11` refusal's reason contains `must be between 1.0 and 10.0`, and the store holds 37 outcomes.
  - `test_one_bad_score_does_not_cost_the_other_rows` — the row after the bad one is created.
  - `test_a_dry_run_writes_nothing_and_reports_the_same_run` — `dry_run=True` twice → the two `as_dict()` are equal, every `created` entry has `outcome_id is None`, `service.get_outcomes(job_id)` is empty, and the event log gained nothing (`repo.list_signals()` / the events count the bulk tests already use).
  - `test_a_dry_run_report_equals_the_write_report_apart_from_ids` — same fixture, dry then write: equal modulo `outcome_id` being filled.
  - `test_a_scored_row_carries_a_manual_claim_check` — every created outcome that has a score has `claim_check.skips[0].reason` from `manual_claim_check()`; an unscored row has `claim_check is None`.
  - `test_theme_names_are_matched_exactly_and_ambiguity_is_reported` — `Onboarding` filings exist, `Retention` appears in `unmatched_themes` with its lines, `Urgent` appears in `ambiguous_themes` with both candidate ids and its lines, and both `Urgent` rows are created unfiled.
  - `test_an_unknown_stage_refuses_the_row_with_the_query_sentence` — reason contains `Unknown stage: collect`.
  - `test_a_stage_with_two_matching_steps_refuses_naming_them` — seed two EXECUTE steps; the refusal lists both ids.
  - `test_a_row_naming_another_job_is_refused` — header `job_id`, one row `job-other`: refused with a reason naming both ids; the other rows still create.
  - `test_an_unknown_step_id_is_refused` — reason comes from `StepNotFoundError`.
  - `test_a_repeat_statement_warns_and_still_writes` — import twice into the same job: second run's `warnings` name the lines and say a second one will be created, and the count in the store doubles.
  - `test_a_repeat_inside_one_file_warns` — a fixture variant with the same statement on lines 2 and 3 warns about line 3 against line 2.
  - `test_duplicate_matching_is_casefolded_and_whitespace_collapsed` — `"  Minimize the TIME  to…"` vs the stored form matches; `"Minimize the time"` vs `"Minimize the time to deploy"` does **not** match.
  - `test_a_row_with_a_non_numeric_score_is_refused_before_any_write` — the `problems` text from Task 1 becomes the refusal reason.
  - `test_a_created_row_never_becomes_a_refusal_and_vice_versa` — `len(created) + len(refused) == 40` for the fixture.
- [x] **Step 2: `uv run pytest packages/core/tests/test_outcome_import.py -q`** → the new tests fail in `import_outcomes` (missing).
- [x] **Step 3: implement the loop** in `outcome_import.py`. Order of operations: one `themes()`, one `steps()`, one `existing_statements()` call; build a name→ids map (case-sensitive) and a stage→steps map once; then per row in file order — pre-validate (row `problems`, bounds per field, `evaluate_outcome_statement`, `JobStage` name, stage→one step, `step_id` existence via `steps()`, `job_id` cell agreement), collect the outcome and its theme name if created, and wrap each write in `try/except OdiError` turning it into a refusal with `str(exc)`. Catch `ImportAbortedError` (raised by a target whose transport died) and stop, filling `aborted` and leaving the rows already written in `created`. File into themes **after** the row loop, one `assign_theme` per matched theme with its whole list of ids. Duplicate warning matching uses a module-level `_canonical(statement) = " ".join(statement.casefold().split())`. A `ParsedTable.problems` short-circuits to a report with zero rows and one refused entry at `line=1` whose reason is the first problem.
- [x] **Step 4: `ServiceImportTarget`** in the same module: `themes` → `service.list_themes(job_id)` (that read already returns the job's themes plus the workspace-wide ones, so one call, not two); `steps` → `service.get_job_map(job_id)`; `existing_statements` → `service.get_outcomes(job_id)`; `add_outcome` → `service.add_outcome(...)` returning `outcome.id`; `assign_theme` → `service.assign_theme(ids, theme_id)`.
- [x] **Step 5: re-export** `ImportReport`, `ImportTarget`, `ServiceImportTarget`, `ImportAbortedError`, `import_outcomes` from `agentic_odi_core`.
- [x] **Step 6: full gates**, then commit `feat(core): import outcome rows with a row-level report (ALH-222)`.

## Task 3: `LocalBackend._add_outcome` accepts an unscored row

**Files:**
- Modify: `apps/cli/src/agentic_odi_cli/backend.py:240-269`
- Test: `apps/cli/tests/test_backend.py` (append)

**Interfaces:**
- Produces for Task 4: `run_tool("add_outcome", args)` working when `args` omits `importance`/`satisfaction`, returning the outcome dict with `importance is None`.
- Consumes: `ODIService.add_outcome`'s optional scores (unchanged), `ToolName.ADD_OUTCOME`'s contract, which already declares both optional.

- [x] **Step 1: write the failing test** in `apps/cli/tests/test_backend.py`:

  ```python
  def test_add_outcome_without_scores_is_created(tmp_path):
      backend = LocalBackend(...)          # the file's existing construction helper
      result = backend.handle({"tool": "add_outcome", "arguments": {
          "job_id": job_id, "statement": WELL_FORMED}})
      assert result["importance"] is None and result["satisfaction"] is None
  ```
  Currently this raises `KeyError: 'importance'`.
- [x] **Step 2: `uv run pytest apps/cli/tests/test_backend.py -k add_outcome -q`** → fails.
- [x] **Step 3: replace `float(args["importance"])` / `float(args["satisfaction"])`** with a local `_score(args, name)` returning `None` when the key is absent or the value is `None`, and `float(value)` otherwise. Leave `_VALUE_RANGE_ERROR` and every other handler untouched — three tests across three apps pin that sentence and it mirrors the tool's own.
- [x] **Step 4: `uv run pytest apps/cli/tests -q`** → pass; the existing scored-path tests are unaffected because `add` always passes both keys.
- [x] **Step 5: full gates**, then commit `fix(cli): an unscored add_outcome through the local backend (ALH-222)`.

## Task 4: `odi desired-outcomes import`

**Files:**
- Modify: `apps/cli/src/agentic_odi_cli/desired_outcomes.py`
- Modify: `apps/cli/src/agentic_odi_cli/render.py`
- Test: `apps/cli/tests/test_outcome_import_cli.py` (new)
- Modify: `docs/cli.md`, `README.md`

**Interfaces:**
- Consumes: Task 1/2 core names; `run_tool`; Task 3's unscored `add_outcome`.
- Produces: the command `desired-outcomes import <path> --job-id <id> [--dry-run] [--json]`; `render_import_report(report: Any, *, as_json: bool) -> str`; a `ToolImportTarget` in `desired_outcomes.py` implementing `ImportTarget` over `run_tool` with `get_job_map`, `list_themes`, `get_outcomes`, `add_outcome`, `assign_theme`.

- [ ] **Step 1: write the CLI tests** using the `CliRunner`/`--db` idiom from `apps/cli/tests/test_bulk_cli.py` (`_invoke`, `_json`, `_seed` patterns; copy their shapes, do not import them across files):
  - dry run of the fixture against a seeded job prints `would create 37` and `refused 3`, exits 0, and `desired-outcomes list` is still empty;
  - `--json` output is the report `as_dict()` and parses;
  - the real run leaves 37 outcomes, and its JSON equals the dry-run JSON with the null ids replaced;
  - a refusal line in human output carries `line 9` and the range sentence;
  - `--job-id` naming no job exits 1 with the `job_not_found` sentence and writes nothing;
  - a path that does not exist exits 1 and names the path;
  - human output after a write run says how to take this back and names `desired-outcomes delete`;
  - the fixture's `Retention` row is reported as unmatched and the two `Urgent` rows as ambiguous.
- [ ] **Step 2: `uv run pytest apps/cli/tests/test_outcome_import_cli.py -q`** → fails (no such command).
- [ ] **Step 3: implement `ToolImportTarget` and the command.** The command reads the file with `Path(path).read_text(encoding="utf-8")`, catches `OSError` into the exit-1 sentence, calls `parse_outcome_table` then `import_outcomes(ServiceOrTool...)` with `dry_run=`, and echoes `render_import_report`. `--dry-run` help text: `Report what this file would do without writing it`. No `--claim-check` option (spec §4).
- [ ] **Step 4: implement `render_import_report`** next to `render_bulk_report`, reusing its `_table` and `_json` helpers: headline `Created N outcome(s)` / `Would create N outcome(s)`, then a `line | statement | reason` table of refusals (`empty="Every row wrote."`), then one line per theme/column note, then warnings.
- [ ] **Step 5: `uv run pytest apps/cli/tests/test_outcome_import_cli.py -q`** → pass.
- [ ] **Step 6: document** the command in `docs/cli.md` where the other `desired-outcomes` commands are listed — including the header table (canonical names, the `outcome`/`need` synonyms, and what is ignored) — and add one line to `README.md`'s capability list.
- [ ] **Step 7: full gates plus `uv run --directory website pytest tests/ -q`** (the CLI-reference completeness test), then commit `feat(cli): odi desired-outcomes import (ALH-222)`.

## Task 5: `POST /api/outcomes/import`

**Files:**
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/router.py`
- Modify: `apps/studio-api/pyproject.toml` (add `python-multipart`)
- Test: `apps/studio-api/tests/test_outcome_import_router.py` (new)

**Interfaces:**
- Consumes: Task 1/2 core names; `router_module.call_mcp_tool`, `_uses_mcp`, `_service`, `_as_http_error`; `StudioErrorCode.MCP_TOOL_FAILED` / `MCP_UNREACHABLE`.
- Produces: multipart route `POST /api/outcomes/import` with fields `file` (`UploadFile`), `job_id`, `dry_run` (default `False`), `mcp_url` (default `""`), returning `dict[str, Any]` — the report's `as_dict()` — exactly as `/outcomes/bulk` returns its report.

- [ ] **Step 1: declare the dependency** in `apps/studio-api/pyproject.toml` under `[project] dependencies`, then `uv lock` and commit the lock hunk with the task; nothing else in the lock changes because `python-multipart` already resolves there.
- [ ] **Step 2: write the failing tests** with `TestClient(create_app(InMemoryRepository(), backend="local"))` and the fixture read as bytes:

  ```python
  files = {"file": ("outcomes.csv", FIXTURE.read_bytes(), "text/csv")}
  data = {"job_id": job_id, "dry_run": "true"}
  response = client.post("/api/outcomes/import", files=files, data=data)
  ```
  - `test_upload_dry_run_reports_and_writes_nothing` — 200, `body["dry_run"] is True`, `created` 37 with null ids, the store empty.
  - `test_upload_writes_the_rows_the_preview_promised` — same body with `dry_run` omitted, ids present, store holds 37.
  - `test_a_refused_row_is_a_two_hundred_with_a_reason` — the `importance=11` line appears in `refused`, never in a 4xx.
  - `test_an_unparseable_file_is_a_two_hundred_with_one_refusal_at_line_one`.
  - `test_an_unknown_job_is_a_404` — `_as_http_error`'s existing shape, no report.
  - `test_a_missing_file_is_a_422`.
  - `test_the_mcp_branch_drives_the_existing_tools` — `monkeypatch.setattr(router_module, "call_mcp_tool", _call)` collecting `(tool, arguments)`: only `add_outcome` and `assign_theme` appear, `assign_theme` is called once per matched theme with a list of ids, and every scored `add_outcome` call carries `manual_claim_check()`.
  - `test_a_tool_refusal_is_a_row_refusal` — the fake raises `StudioHTTPError(StudioError(code=MCP_TOOL_FAILED, message="…"))` for one row: that row is refused, the run continues.
  - `test_an_unreachable_server_aborts_the_run` — the fake raises `StudioHTTPError(... MCP_UNREACHABLE ...)` at row 20: earlier rows stay in `created`, `aborted` names line 20, and `refused` does not contain 20 invented entries.
- [ ] **Step 3: `uv run pytest apps/studio-api/tests/test_outcome_import_router.py -q`** → fails (404, no route).
- [ ] **Step 4: implement the route.** Parse bytes with `parse_outcome_table(await file.read())`. `_uses_mcp(request)` selects an `McpImportTarget` (an inner class over `call_mcp_tool` for the five `ImportTarget` methods, translating `MCP_TOOL_FAILED` into `OdiError` so the loop refuses the row and `MCP_UNREACHABLE` into `ImportAbortedError` so the loop stops); otherwise `ServiceImportTarget(_service(request))`. Wrap the whole call in the router's existing `except Exception as exc: raise _as_http_error(exc) from exc` so an unknown job still becomes the 404 the other routes give.
- [ ] **Step 5: re-run the file's tests** → pass; then `uv run pytest apps/studio-api/tests -q` for regressions in the router suite.
- [ ] **Step 6: full gates**, then commit `feat(studio-api): upload a CSV of outcomes (ALH-222)`.

## Task 6: regenerate the OpenAPI artifacts

**Files:**
- Modify: `apps/studio/openapi.json`, `apps/studio/src/api/schema.d.ts`

- [ ] **Step 1: dump** `create_app(InMemoryRepository(), backend="local").openapi()` into `apps/studio/openapi.json` with `json.dumps(..., indent=2)`, matching the committed shape, then confirm the diff adds only the import route.
- [ ] **Step 2: `cd apps/studio && npm run gen:api-types`.**
- [ ] **Step 3: prove currency:** run Step 2 again with `git diff --exit-code -- src/api/schema.d.ts`; then `npx tsc -b --noEmit`, `npx eslint .`, `npx vitest run` (no TS source changes, so all three must be unchanged-green).
- [ ] **Step 4: commit** `chore(studio): regenerate OpenAPI for the outcome import route`.

## Task 7: the two doors must not disagree

**Files:**
- Test: `apps/studio-api/tests/test_outcome_import_router.py` (append)

- [ ] **Step 1: write the contract test** — `test_the_cli_and_the_upload_report_the_same_run`: build the same seeded job twice, once through `import_outcomes(... ServiceImportTarget ...)` and once through `TestClient` upload with `dry_run=true`, and assert the two `as_dict()` are equal for `refused`, `unmatched_themes`, `ambiguous_themes`, `warnings` and the `created` statements/lines. This is the criterion the design exists to satisfy; if someone forks the loop into the router, it goes red here.
- [ ] **Step 2: run it** (`uv run pytest apps/studio-api/tests/test_outcome_import_router.py -q`) → pass; fix the loop, not the assertion, if it does not.
- [ ] **Step 3: add the In-flight line to `docs/roadmap.md`**: **Import a spreadsheet of outcomes** — `odi desired-outcomes import` and `POST /api/outcomes/import` share one parser and one row-level report, a bad row is refused with its line number while the rest write, and `--dry-run` previews the run without writing it (this change) — following the "In flight" section's existing style.
- [ ] **Step 4: full gates**, `uv run python scripts/doc_check.py`, then commit `test(studio): the import reports the same run through both doors (ALH-222)`.

---

## Self-review notes

- **Spec coverage:** the design's decisions 1–8 land in Tasks 1–5 (target job, synonyms, ambiguous names, manual claim check, stage, one loop/three targets, duplicates, no undo), the report table in Task 2, the fixture list in Tasks 1–5 and 7. `docs/cli.md` and `README.md` are Task 4 Step 6; the architecture registration is Task 1 Step 7; OpenAPI is Task 6.
- **Deferred to ALH-223:** `fmt` accepts `"csv"` only and names that word in its refusal — the XLSX sibling inherits `ImportRow` unchanged.
- **Type consistency:** `ImportTarget`'s five method names are the ones Tasks 4 and 5 implement; `ImportReport.as_dict()` keys are the ones Tasks 4, 5 and 6 render, type and document.
