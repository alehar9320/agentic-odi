# ALH-223 · Optional XLSX Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read an `.xlsx` workbook into the exact rows ALH-222's parser already produces, so one validator and one report serve a CSV and a spreadsheet through both the CLI and the Studio upload — with openpyxl as an optional extra that names itself when the build lacks it.

**Architecture:** `packages/core/.../outcome_import.py` splits at the one place the two formats genuinely differ: where the rows come from. `read_rows` (csv) and `read_xlsx_rows` (openpyxl) both return `TableLines` — `(row number, cells)` pairs plus the coordinates that held a formula with no stored value — and `_build_rows` is ALH-222's header/synonym/`_number`/problems loop, moved unchanged. `import_outcomes`, `ImportTarget`, `ImportReport` and every refusal sentence stay as they are; the loop never learns which format it is reading, so the MCP branch still drives the same six tools.

**Tech Stack:** Python 3.10+ (stdlib `csv`, `zipfile`, `xml.etree` for the fixtures), `openpyxl` behind `[project.optional-dependencies] xlsx`, Typer, FastAPI + `python-multipart`, pytest, React/TS artifacts regenerated only.

**Spec:** `docs/superpowers/specs/2026-11-04-alh-223-xlsx-import-design.md`

## Global Constraints

- One validator. No row-shape rule, synonym, `_number` behaviour or refusal sentence is duplicated for the workbook path; `_build_rows` is moved, not copied.
- Stored values only. Nothing evaluates a formula, and nothing reads a sheet the person did not name when more than one has rows.
- A score that cannot be read is refused with its cell address; it never becomes "unscored". An unreadable optional cell is read as empty and warned about once per file.
- Refusal `line` for a workbook is the sheet's own row number, header on row 1 — the number the person sees in their spreadsheet app.
- `openpyxl` is imported **inside** the reader function under a guard. A module-level import makes `agentic_odi_core` unimportable without the extra.
- The two new errors and the retargeted `UnsupportedFormatError` subclass core `ValidationError`, whose `error_status()` entry is 400; an unknown `OdiError` maps to **500** and a wrong suffix or a missing extra is not a server fault.
- No MCP tool is added, no `ToolName`, no `TOOL_SPECS` edit, no `mcp_server.py` edit.
- No test reaches the network, and the absent-extra path is tested by blocking the import, never by uninstalling.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy apps brand packages`, `uv run pytest -q` (**2224 passed** at branch start), `uv run python scripts/doc_check.py`, `uv run python scripts/check_version_parity.py`, `uv run --directory website pytest tests/ -q` (283) pass at the end of every task; in `apps/studio`, `npx tsc -b --noEmit`, `npx eslint .`, `npx vitest run` (1073) pass at the end of the task that touches generated artifacts.
- `docs/cli.md` keeps pace with the CLI (`website/tests/test_generated.py::test_the_cli_reference_mentions_every_registered_command`), and `README.md` is updated in the same task that changes a capability.

## Review Focus

Inputs no task's own deliverable would otherwise exercise, and what a person is owed when they arrive:

1. **A score column that is a formula Excel never recalculated.** Expect: that row is refused naming `B12` and telling them to paste values; the other rows write; the outcome is never filed unscored. Pinned in Task 2.
2. **A workbook with a tab per quarter.** Expect: no import, and a refusal naming every sheet that has rows plus how to name one. Never the tab Excel marked active. Pinned in Task 2, again in Tasks 3 and 4 at each door.
3. **This build, without the extra.** Expect: CSV still imports; a workbook answers the install sentence — exit 1 in the terminal, a 400 envelope on the upload — with no traceback, no report, nothing written. Pinned in Tasks 3 and 4.
4. **Numbers as Excel stores them.** Expect: `7.0` reads as `7` so the same row parses the same from either format; a date in a score column is refused by the existing `_number` sentence, not a new one. Pinned in Task 2.
5. **The same rows in both formats.** Expect: byte-identical reports including the refused line numbers. Pinned in Task 6, the last task, because it is the criterion the issue's first line names.

---

## Task 1: Declare the optional dependency honestly

**Files:**
- Modify: `packages/core/pyproject.toml`
- Modify: `pyproject.toml` (root, `[dependency-groups] dev`)
- Modify: `uv.lock`
- Modify: `scripts/build_binary.sh:40`
- Modify: `docs/architecture/README.md` (the core row of the layer table)

**Interfaces:**
- Produces for Tasks 2–6: `openpyxl` importable in the test environment, and `agentic_odi-core[xlsx]` as the name a person installs.
- Consumes: nothing.

- [ ] **Step 1: add the extra** to `packages/core/pyproject.toml`:

  ```toml
  [project.optional-dependencies]
  xlsx = ["openpyxl>=3.1"]
  ```

- [ ] **Step 2: pin it for the suite** in the root `pyproject.toml` `[dependency-groups] dev`, `openpyxl==3.1.5` (the version `uv pip install --dry-run openpyxl` resolves, alongside `et-xmlfile==2.0.0`), keeping the list's alphabetical placement, then run `uv lock`. The lock hunk rides in this commit; nothing else in `uv.lock` should move.

- [ ] **Step 3: prove the extra is invisible to the architecture gate.** `uv run pytest tests/test_architecture.py -q` → all pass. That test reads only each member's `[project] dependencies` block and compares *workspace* edges, so an optional extra cannot invent a phantom `core -> openpyxl` arrow. If it now fails, the assumption in the spec's Constraints section was wrong and this task stops there.

- [ ] **Step 4: carry the reader into the frozen bundle.** `scripts/build_binary.sh:40` runs `uv sync --all-packages --locked` before PyInstaller; add `--all-extras`. A PyInstaller onedir cannot `pip install` an extra at runtime, so the released CLI either reads workbooks or tells the person to save CSV, and the bundle must not be the reason it says the second. Verify the flag combination is accepted by running just that line (`uv sync --all-packages --all-extras --locked` → resolves from the lock, no network); if uv rejects it, append `--package agentic-odi-core --extra xlsx` to a second sync line instead and say so in the commit body.

- [ ] **Step 5: name the rule where the layers are documented.** One sentence in the `packages/core` row of `docs/architecture/README.md`: the `xlsx` extra is optional, openpyxl is imported inside `outcome_import.read_xlsx_rows`, and nothing outside that function may import it. Then `uv run python scripts/doc_check.py` and `uv run python scripts/check_version_parity.py` → exit 0.

- [ ] **Step 6: run the gates** (Global Constraints), then commit `build(core): declare openpyxl as the optional xlsx extra (ALH-223)`.

## Task 2: The reader, in `outcome_import.py`

**Files:**
- Modify: `packages/core/src/agentic_odi_core/outcome_import.py`
- Modify: `packages/core/src/agentic_odi_core/__init__.py` (re-export the two new errors)
- Create: `packages/core/tests/fixtures/xlsx_workbook.py` (helper, not a test — no `test_` prefix, so pytest does not collect it)
- Modify: `packages/core/tests/test_outcome_import.py`

**Interfaces:**
- Consumes: ALH-222's `ImportRow`, `ParsedTable`, `_normalise`, `_number`, `STATEMENT_HEADERS`, `NUMERIC_FIELDS`, `TEXT_FIELDS`, `IGNORED_HEADERS`, `UnsupportedFormatError`.
- Produces for Tasks 3–6:

  ```python
  XLSX_FORMAT = "xlsx"                       # plus READABLE_FORMAT = "csv"
  FORMATS = ("csv", "xlsx")

  class XlsxExtraMissingError(ValidationError): ...
  class SheetSelectionError(ValidationError): ...

  @dataclass(frozen=True)
  class TableLines:
      lines: list[tuple[int, list[str]]]                     # (row number, cells as text)
      formula_cells: dict[int, list[int]] = field(...)       # row number -> 0-based columns that
                                                             # held a formula with no stored value

  def read_rows(source: str | bytes) -> TableLines
  def read_xlsx_rows(source: bytes, sheet: str | None = None) -> TableLines
  def format_for_name(filename: str) -> str          # ".csv"/"" -> "csv", ".xlsx" -> "xlsx",
                                                     # anything else -> UnsupportedFormatError
  def parse_outcome_table(
      source: str | bytes, fmt: str = READABLE_FORMAT, sheet: str | None = None
  ) -> ParsedTable

  @dataclass
  class ParsedTable:
      rows: list[ImportRow]
      ignored_columns: dict[str, str]
      problems: list[str]
      warnings: list[str] = field(default_factory=list)   # NEW: the file's own condition
  ```

  and one changed base class: `class UnsupportedFormatError(ValidationError)` (was `OdiError`), so a wrong suffix answers 400 on the upload door.

- [ ] **Step 1: extract the CSV reader.** Write the failing test `test_read_rows_numbers_like_the_parser_did` asserting `read_rows(FIXTURE.read_bytes()).lines[0][0] == 1` and that a file with a blank line in the middle keeps the following row's number. Then move `outcome_import.py:102-103`'s decode-plus-`csv.reader` into `read_rows`, returning every `(reader.line_num, cells)` pair **including blank lines** (the loop's blank-skip moves to `_build_rows`, which is where the CSV path and the workbook path can share it). `parse_outcome_table` keeps its `fmt` check and now calls `_build_rows(read_rows(source).lines)`. Run `uv run pytest packages/core/tests/test_outcome_import.py -q` — every ALH-222 test still green, unchanged, including the three that assert `line` 9/18/27 and the blank-line cases.

- [ ] **Step 2: write the workbook helper.** `packages/core/tests/fixtures/xlsx_workbook.py` builds workbook **bytes** with stdlib `zipfile` and hand-written XML, so a test states what a file contains instead of committing a binary:

  ```python
  @dataclass
  class Formula:
      text: str                     # "=SUM(A1:A2)"
      cached: object | None = None  # the stored value, or None for a formula never calculated

  def workbook_bytes(sheets: dict[str, list[list[object]]]) -> bytes
  def xlsx_from_csv(text: str, sheet: str = "Outcomes") -> bytes   # openpyxl, see Step 5
  ```

  `workbook_bytes` writes `[Content_Types].xml`, `_rels/.rels`, `xl/workbook.xml`,
  `xl/_rels/workbook.xml.rels` and one `xl/worksheets/sheetN.xml` per entry, each cell carrying an
  explicit `r="B2"` address so a hole keeps its column: `str` → `t="inlineStr"`, `int/float` →
  `<v>` with `repr`, `None` → no `<c>` at all, `Formula` → `<f>` (the text without `=`) plus `<v>`
  only when `cached is not None`. A row that is `None` is a fully blank sheet row.
  `xlsx_from_csv` opens the CSV text with `csv.reader` and writes it out with `openpyxl`, turning a
  cell into a `float` when the text parses as one and leaving it text otherwise — that is what
  "Save as" does, so the equivalence claim compares values, not strings.
  Prove the helper before relying on it: `uv run python -c` that `load_workbook` reads back
  `workbook_bytes({"Q3": [["statement", 7.0], ["need", Formula("=SUM(A1:A2)")]]})` and reports
  `data_only=True` → `(7.0, None)`, `data_only=False` → `("=SUM(A1:A2)", None)`. If openpyxl refuses
  the file, the helper is missing a part; fix the helper, do not commit a binary.

- [ ] **Step 3: write the sheet-selection tests** (fail first — `read_xlsx_rows` does not exist). Verbatim sentences, `wb.sheetnames` order, names stripped before comparison:

  - `test_one_sheet_with_rows_is_read_without_being_named` — a workbook with rows in `Q3` and a truly empty second sheet yields its rows, header on row 1.
  - `test_two_sheets_with_rows_refuse_and_name_them` — `this workbook has rows in 3 sheets (Q3, Backlog, Notes); name the one to read with --sheet`, as `SheetSelectionError`, and the same bytes with `sheet="Backlog"` read that tab.
  - `test_an_unknown_sheet_names_the_ones_that_exist` — `no sheet named "Backlog" in this workbook; it has Q3, Notes`.
  - `test_a_named_empty_sheet_refuses` — `sheet "Notes" has no rows; nothing to import`.
  - `test_a_workbook_with_no_rows_anywhere_refuses` — `this workbook has no rows in any sheet; nothing to import`.
  - `test_a_blank_row_keeps_its_sheet_number` — rows before and after a blank keep their gutter numbers; the blank yields no `ImportRow`.

- [ ] **Step 4: implement `read_xlsx_rows`.** Guarded function-level import, `load_workbook(io.BytesIO(source), data_only=True)` (never `read_only`: the second pass needs random access to the same coordinates), select the sheet per Step 3, then build `lines` from `ws.iter_rows(values_only=True)` starting at row 1, stringing each cell: `None`/empty → `""`, a float with no fractional part → `str(int(value))` so `7.0` reads as `7`, `7.5` → `"7.5"`, anything else → `str(value)`. Record the 0-based coordinates of every cell that came back empty **in a row that has other content**. If that set is non-empty, load once more with `data_only=False` and, for those coordinates only, add to `formula_cells` the ones whose `ws2.cell(row=..., column=...).data_type == "f"`. `XlsxExtraMissingError` is raised from the guarded import with the exact sentence:

  > `reading a .xlsx needs the optional xlsx extra: pip install 'agentic-odi-core[xlsx]' — or save the workbook as CSV, which this build reads without it`

  and is raised as a plain error, not with a `ModuleNotFoundError` `__cause__` that would print a traceback above the sentence at either door. `test_the_absent_extra_is_blocked_without_a_network` uses `monkeypatch.setitem(sys.modules, "openpyxl", None)`, which makes the guarded import raise, so no test uninstalls anything.

- [ ] **Step 5: make the two formats agree in `_build_rows`.** Write the failing tests, then implement:

  - `test_an_uncached_formula_refuses_its_row_naming_the_cell` — `Formula("=B7+C7")` in the `importance` column of sheet row 12 puts this exact string in that row's `problems` and nowhere else: `cell B12 is a formula with no stored value; this import reads stored values and never computes them — paste it as values and import again`; its neighbours parse; `_column_letter(index)` maps 1 → `B`, 26 → `Z`, 27 → `AA`.
  - `test_an_uncached_formula_in_an_optional_column_warns_instead` — the same in `theme` and `stage` yields no refusal and exactly one `ParsedTable.warnings` entry: `3 optional cells hold a formula with no stored value (theme, stage); they were read as empty` (count = cells, names in header order, listed once).
  - `test_a_formula_with_a_stored_value_is_read_as_that_value` — `Formula("=AVERAGE(A1:A9)", cached=7.5)` reads `7.5`, one load, and nothing says it was ever a formula.
  - `test_a_clean_workbook_is_opened_once` — count loads through a stub module placed in `sys.modules` under `monkeypatch.setitem` that exposes `load_workbook = counting_wrapper(openpyxl.load_workbook)` (the guarded function-level import is what makes this observable): one call for a fully populated workbook whose `Formula` cells all carry a cached value, two for the same file with one cell left empty.
  - `test_a_date_in_a_score_column_is_refused_by_the_number_rule` — no new sentence; `_number`'s `importance must be a number, got "..."` with `str()` of the datetime.
  - `test_the_equivalence_workbook_has_the_same_rows_as_the_csv` — `xlsx_from_csv(FIXTURE.read_text())` and the CSV produce the same `lines` text, so `_build_rows` cannot tell them apart.
  - `test_parse_outcome_table_routes_xlsx_to_the_workbook_reader` — `fmt="xlsx"` (and `"XLSX "`) dispatches; `fmt="xls"` still raises `UnsupportedFormatError` with ALH-222's sentence, and that class is now a `ValidationError` (`assert issubclass(UnsupportedFormatError, ValidationError)`, plus `error_status(UnsupportedFormatError("x")) == 400`).
  - `test_a_csv_handed_a_sheet_is_refused` — `parse_outcome_table(text, sheet="Backlog")` raises `SheetSelectionError("a CSV has no sheets; --sheet is for a .xlsx workbook")`.
  - `test_format_for_name_is_the_rule_both_doors_share` — `"out.CSV"` and `"out.csv"` and a bare `"out"` → `READABLE_FORMAT`; `"wb.XLSX"` → `XLSX_FORMAT`; `"wb.xls"` raises `UnsupportedFormatError` whose message names `'.xls'`; `"notes.txt"` → same, naming `'.txt'`. Neither door writes its own version of this.
  - `import_outcomes` puts `parsed.warnings` **before** its own duplicate-statement warnings, and `ImportReport.as_dict()` grows no key (`warnings` already exists). `test_the_report_lists_file_warnings_before_store_warnings` pins the order with a fixture that has both.

- [ ] **Step 6: run the gates** — `uv run pytest packages/core/tests/test_outcome_import.py -q`, then the full set, `uv run pytest -k xlsx -q` twice offline. Commit `feat(core): read an XLSX workbook into the same rows (ALH-223)`.

## Task 3: The terminal door

**Files:**
- Modify: `apps/cli/src/agentic_odi_cli/desired_outcomes.py:185-220`
- Modify: `docs/cli.md` (the import section, beside the header table)
- Modify: `README.md` (the import capability bullet)
- Modify: `apps/cli/tests/test_outcome_import_cli.py`

**Interfaces:**
- Consumes: `parse_outcome_table(source, fmt, sheet)`, `XlsxExtraMissingError`, `SheetSelectionError`, `UnsupportedFormatError`. The CLI's tests build the workbooks they hand to the command with `openpyxl` (in the root `dev` group from Task 1, so installed and offline) saved into `tmp_path` — a CLI test asserts the door, not the XML, and does not import core's fixture helper across suites.
- Produces for Task 4: nothing shared — the format rule is core's `format_for_name` (Task 2) — but the door's own precedent that a format problem is a sentence on stderr with exit 1, never a report.

- [ ] **Step 1: write the failing CLI tests** in `apps/cli/tests/test_outcome_import_cli.py`, reusing that file's existing seeded-store fixture:
  - `test_import_reads_an_xlsx_and_the_same_csv_agree` — the same rows written both ways, `--dry-run --json` twice, and the two bodies are equal, `refused` line numbers included.
  - `test_the_sheet_flag_picks_the_tab` — a three-tab workbook with `--sheet Backlog` imports those rows only.
  - `test_an_ambiguous_workbook_exits_one_and_names_the_tabs` — exit 1, the refusal sentence on stderr, `Error: ` prefix, nothing written to the store.
  - `test_a_missing_extra_exits_one_with_the_install_sentence` — `monkeypatch.setitem(sys.modules, "openpyxl", None)`, exit 1, the sentence, no traceback text in the output.
  - `test_a_suffix_that_is_not_a_spreadsheet_is_refused` — `import notes.txt` exits 1 with `UnsupportedFormatError`'s sentence.

- [ ] **Step 2: implement the command.** `import_file` gains
  `sheet: str | None = typer.Option(None, "--sheet", help="Read that sheet; required when the workbook holds rows in more than one")`,
  gets its `fmt` from core's `format_for_name(path)` — so the terminal never holds its own copy of
  "what format is this file", and an unknown suffix raises the same `UnsupportedFormatError` naming
  the suffix that was tried — and passes `sheet` (or `None` when the flag is empty, which is how
  Typer delivers an unfilled `str | None`). `parse_outcome_table` is then called inside one
  `except (XlsxExtraMissingError, SheetSelectionError, UnsupportedFormatError)` that echoes
  `Error: {exc}` to stderr and `raise typer.Exit(code=1)`, the same shape as `export`'s
  unknown-format branch at `desired_outcomes.py:117-119`. The docstring gains the sentence that a
  workbook is read for its stored values, that formulas are never computed, and that more than one
  sheet with rows must be named.

- [ ] **Step 3: publish it.** `docs/cli.md`: an XLSX paragraph beside the header table — one sheet with rows is read, more than one must be named with `--sheet`, formulas are read as stored values or the row is refused, and `pip install 'agentic-odi-core[xlsx]'` is what makes a workbook readable at all. `README.md`: the import bullet becomes "a CSV or an `.xlsx`" with the extra named. `uv run --directory website pytest tests/test_generated.py -q` → the CLI reference test passes.

- [ ] **Step 4: run the gates** and read one run by hand: `uv run odi desired-outcomes import <workbook> --job-id <id> --dry-run` for a one-sheet file, a three-sheet file (refusal names the tabs), `--sheet Backlog`, and the same after blocking openpyxl (the install sentence, no traceback). Commit `feat(cli): odi desired-outcomes import reads .xlsx (ALH-223)`.

## Task 4: The upload door

**Files:**
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/router.py` (the `/outcomes/import` handler)
- Modify: `apps/studio-api/tests/test_outcome_import_router.py`

**Interfaces:**
- Consumes: `XLSX_FORMAT`, the three errors, `_as_http_error` (which already routes any core `OdiError` through `error_status()` + `code_for_status()`; core `ValidationError` → **400**, code `validation`).
- Produces for Task 5: the request body's shape — a `file` part with a filename and a `sheet` form field.

- [ ] **Step 1: write the failing tests** in `apps/studio-api/tests/test_outcome_import_router.py`, reusing `_seeded_service`, `_install_mcp`, `REFUSED_LINES`:
  - `test_the_same_rows_as_xlsx_report_the_same_run_as_csv` — `_upload(client, job_id, file_name="outcomes.xlsx", body=xlsx_bytes)` and the CSV upload produce the same body, key for key.
  - `test_the_sheet_field_selects_the_tab` and `test_an_ambiguous_workbook_is_a_400_naming_the_tabs` — status 400, `error.code == "validation"`, the sentence in the body, `service.get_outcomes(job_id) == []`. **A sheet problem is a bad request, so it is an envelope, never a 200 report holding one refusal** — the rule ALH-222 set for an unknown job.
  - `test_a_missing_extra_is_a_400_envelope_not_a_report` — openpyxl blocked, 400, the install sentence, no `created`/`refused` keys at all.
  - `test_a_suffix_neither_door_reads_is_a_400` — `notes.txt` → envelope, not the line-1 report ALH-222 pins for a CSV missing a header.
  - `test_the_mcp_branch_still_drives_only_the_six_tools` — the workbook upload over `backend="mcp"`; the sorted `{tool for tool, _ in calls}` set equals ALH-222's, proving the parse happens here and not on the server.

- [ ] **Step 2: implement the handler.** `file: bytes = File(...)` becomes `file: UploadFile = File(...)` (read with `file.file.read()`; the handler stays a plain `def`, so the threadpool and the existing `asyncio.run` bridge are untouched), plus `sheet: str = Form("")`. A shared call to core's `format_for_name(file.filename)` decides the format — the same call the CLI makes, so a file cannot get two answers depending on which door it came through — and `sheet or None` is passed straight down. The existing `except Exception as exc: raise _as_http_error(exc)` already turns the three `ValidationError` subclasses into 400 envelopes; confirm no branch above it swallows them (`_import_failure` is only for the MCP loop, not the parse).

- [ ] **Step 3: run the gates** — `uv run pytest apps/studio-api/tests/test_outcome_import_router.py -q`, then the full set. Commit `feat(studio-api): accept an .xlsx upload (ALH-223)`.

## Task 5: Regenerate the artifacts

**Files:**
- Modify: `apps/studio/openapi.json`
- Modify: `apps/studio/src/api/schema.d.ts`

- [ ] **Step 1: dump the spec in-process** — the ALH-222 route worked: a throwaway script at an absolute path writing `json.dumps(create_app(InMemoryRepository(), backend="local").openapi(), indent=2) + "\n"` to `apps/studio/openapi.json`, run as `uv run python /tmp/dump_studio_openapi.py` from the repo root. Do not hand-edit. The diff should show only the import route's request body: a `file` part whose schema is binary-string-with-filename semantics, and a new optional `sheet` string.

- [ ] **Step 2: regenerate the types** — `npm run gen:api-types` in `apps/studio`, then run it a second time and `git diff --exit-code -- src/api/schema.d.ts` → no output, which is the currency proof CI checks.

- [ ] **Step 3: run the frontend gates** — `npx tsc -b --noEmit`, `npx eslint .` (0 errors, the 5 standing react-refresh warnings), `npx vitest run` (1073). Then the root gates. Commit `chore(studio): regenerate OpenAPI for the .xlsx upload (ALH-223)`.

## Task 6: The equivalence claim, and the roadmap

**Files:**
- Modify: `packages/core/tests/test_outcome_import.py`
- Modify: `docs/roadmap.md`

- [ ] **Step 1: write the test the issue's first acceptance line asks for.** `test_an_xlsx_and_a_csv_of_the_same_rows_report_the_same_run` — seed the job the way both suites already do (one `EXECUTE` step, `Onboarding` on the job, `Urgent` on the job **and** workspace-wide), run `import_outcomes` twice against the same `ServiceImportTarget`-equivalent store: once over `parse_outcome_table(FIXTURE.read_bytes())`, once over `parse_outcome_table(xlsx_from_csv(FIXTURE.read_text()), fmt="xlsx")`. Assert the two `as_dict()` bodies are equal — `created` (statements, scores, filed themes), `refused` (line numbers 9, 18, 27 and the service's own sentences), `unmatched_themes`, `ambiguous_themes`, `warnings`, `aborted is None` — and that the stored outcomes match field for field. Then the dry-run variant: `dry_run=True` on the workbook writes nothing, and one bad row does not abort the run.

- [ ] **Step 2: put it on the roadmap.** Extend the ALH-222 In-flight line you added, or add the sibling line **Import an XLSX workbook too** — one validator, both doors, an optional `xlsx` extra that names itself when the build lacks it, stored values only, never a guessed sheet (this change). `uv run python scripts/doc_check.py` → exit 0.

- [ ] **Step 3: run every gate** in Global Constraints, plus `uv run pytest -k "xlsx or import" -q` twice offline. Commit `test(core): an .xlsx and a .csv of the same rows report the same run (ALH-223)`.

## Ship

`git push -u origin qoder/ALH-223-xlsx-import`; PR base `qoder/ALH-222-csv-import` (stacked), title `feat: read optional XLSX imports through the CSV validation path`. Body: what the issue promised (no second validator), the design's calls with the worksheet and formula rules flagged as mine, a `Reuses:` block per `docs/architecture/reuse.md` — rung 1: `parse_outcome_table`'s header/synonym/ignored-column rules, `_number`, `_row_problem`, `ImportReport`, `render_import_report`, `_as_http_error`/`error_status`; rung 2: `openpyxl` as a declared optional extra rather than a hand-rolled zip/XML reader, and stdlib `zipfile` + `xml.etree` only for the two cases openpyxl cannot write (an uncached `<f>` cell, a sheet with a blank row) — then the Verification numbers. Linear ALH-223 → In Review with the PR link in the same comment (`commentCreate` with the vars wrapped in `{"input": {…}}`). Do not wait for CI; afterwards re-check `gh pr view 721 --json mergeable,mergeStateStatus` and this PR's for conflicts, and post ALH-222's missing comment if it is still outstanding.

## Verification

Root: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy apps brand packages`, `uv run pytest -q` (2224 at branch start, more at the end), `uv run python scripts/doc_check.py`, `uv run python scripts/check_version_parity.py`, `uv run --directory website pytest tests/ -q`.
`apps/studio`: `npx tsc -b --noEmit`, `npx eslint .`, `npx vitest run`.
Read by hand (Task 3 Step 4): a one-sheet workbook dry run, a three-sheet refusal naming the tabs, `--sheet Backlog`, the same file with openpyxl blocked → the install sentence and no traceback, and the same workbook uploaded → 400 envelope.
Offline proof: `uv run pytest -k xlsx -q` twice with the network unreachable.
