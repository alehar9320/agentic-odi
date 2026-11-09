# ALH-223 · M2-04.2 — Read optional XLSX imports through the CSV validation path: Design

**Linear:** ALH-223 · M2-04.2 "Read optional XLSX imports through the CSV validation path"
**Repo:** `alehar9320/agentic-odi`, workspace `shrimpfish`
**Date:** 2026-11-04
**Status:** ready for review. The readiness blocker ("choose worksheet-selection behavior and
handling of formula cells/multiple nonempty sheets; never guess a sheet or compute formula results
that are not stored values") is answered below, and every answer is marked as my call rather than
something you agreed to. You chose the reader: **openpyxl, as an optional extra, not a mandatory
dependency.** Strike any call here and the shape changes.

**Depends on:** ALH-222 (M2-04.1, PR #721), which built `parse_outcome_table`, `import_outcomes`
and `ImportReport` and left one door standing: `UnsupportedFormatError` at
`packages/core/src/agentic_odi_core/outcome_import.py:98`. This increment opens that door. It adds
no validator, no loop, no report field beyond one list, and no MCP tool.

## Intent and the why

A person doing job mapping keeps their research in a spreadsheet — the file they are handed is
`.xlsx`, it has a tab per quarter, and the score column is a `=AVERAGE()` someone left in.
ALH-222 gave them a CSV door, which means the honest instruction today is "save as CSV first".
That works, and it is also a step they should not have to take, and one they will take wrong
(saving the wrong tab, losing a column they did not see was hidden).

So this increment is: read the workbook they already have, and hand its rows to the *same*
validator, the same loop and the same report the CSV path uses. The issue's own framing is the
whole spec — *"without maintaining a second validator"*. A second validator is how two doors start
disagreeing, which is the thing ALH-222 exists to prevent.

## Goals

- `odi desired-outcomes import workbook.xlsx --job-id <id> [--sheet Q3] [--dry-run] [--json]`
  imports a workbook.
- `POST /api/outcomes/import` accepts an `.xlsx` part and reports the identical run.
- An equivalent workbook and CSV — the same rows, the same columns — produce the same `created`,
  `refused`, `unmatched_themes`, `ambiguous_themes` and `warnings`, and the same stored outcomes.
- Nothing about the format is mandatory: a build without the `xlsx` extra still imports CSV, and
  names the extra it is missing when asked for a workbook.
- Stored values only. An import never computes a formula, never guesses a sheet, and never turns a
  score it cannot read into "unscored".

## Non-goals

- Writing a workbook, exporting one, or `export --format xlsx`. Read-only, as the issue says.
- Evaluating formulas. There is no spreadsheet engine here and none gets added.
- Reading more than one sheet in a run, or merging tabs. One file, one sheet, one run.
- Cell styles, conditional formatting, charts, named ranges, formulas-as-text, `.xls`, `.ods`,
  Google Sheets' API, and the Studio drop-zone UI (still ALH-222's non-goal).
- Any change to the MCP server's tool surface, and any change to what a row means: the columns,
  their synonyms, and their refusals are ALH-222's and stay untouched.

## Anti-goals

- A second validation path. The moment a workbook row is checked by different code than a CSV row
  is, the two doors disagree and the person finds out from their store.
- Guessing a sheet. Reading whichever tab Excel marked active is how forty rows of `Notes` get
  filed against a job as desired Outcomes — with no undo token to take back.
- Silently reading an uncached formula as empty in a score column. That turns "7.5" into "no score
  entered", which the store then reports as unmeasured research the person believes they measured.
- Making openpyxl a runtime requirement. The core package is imported by the MCP server, the
  sidecar, the CLI and tests; a spreadsheet library in that path is a dependency nobody asked for
  until they hand over a workbook.
- A traceback where a sentence belongs: an absent extra must name the install path, not show a
  `ModuleNotFoundError` stack.

## Constraints

- `parse_outcome_table(source, fmt)` is the shared entry both doors already call; its row loop,
  `_number`, `_row_problem`, `ImportRow.problems` and `ImportReport` are the machinery this
  increment feeds rather than forks.
- Core modules are registered in `tests/test_architecture.py::CORE_LAYERS` and the layer table in
  `docs/architecture/README.md`. No new module is needed: the reader joins `outcome_import.py`,
  which is already methodology.
- `tests/test_architecture.py` compares *declared workspace edges* to *observed workspace imports*
  and reads only the `[project] dependencies` block, so an `[project.optional-dependencies]`
  entry cannot invent a phantom edge. Third-party imports are outside its scope (verified against
  the parser, not assumed).
- `error_status()` in `errors.py` sends an unknown `OdiError` to **500**. The two new errors
  therefore subclass core's `ValidationError`, whose table entry is 400, so an upload answers with
  the shared envelope the way ALH-197's refused bulk run does — and never a 500. (A 415 would need
  a new entry in the contract layer's status table for one route, and the body already names the
  exact install path.)
- `scripts/build_binary.sh:40` runs `uv sync --all-packages --locked` before PyInstaller. A frozen
  bundle cannot `pip install` an extra later, so the release build must carry the reader.
- Tests must not reach the network (`uv run pytest -k xlsx` twice, offline, green) and must not
  require uninstalling a package to exercise the absent path.
- `docs/cli.md` must keep pace with the CLI:
  `website/tests/test_generated.py::test_the_cli_reference_mentions_every_registered_command`.
- Generated artifacts: `apps/studio/openapi.json` and `src/api/schema.d.ts` are regenerated, not
  hand-edited, and CI proves they are current.

## The decisions the readiness blocker asked for

### 1. Worksheet selection: read it when exactly one sheet has rows; never otherwise

One sheet with rows in it is not a guess, so it is read. Two or more is a question only the person
can answer, and the answer is a named flag, not a fall-back to whichever tab the workbook marks
active.

| Situation | Behaviour | The sentence |
|---|---|---|
| exactly one sheet has rows | read it | — |
| two or more sheets have rows, none named | refuse | `this workbook has rows in 3 sheets (Q3, Backlog, Notes); name the one to read with --sheet` |
| one sheet named, it exists and has rows | read it | — |
| one sheet named, no such sheet | refuse | `no sheet named "Backlog" in this workbook; it has Q3, Notes` |
| one sheet named, empty | refuse | `sheet "Notes" has no rows; nothing to import` |
| no sheet has rows | refuse | `this workbook has no rows in any sheet; nothing to import` |

A fully blank row is skipped, and a row whose only cells are empty strings is skipped, exactly as
the CSV path skips a blank line. Sheet names are compared after stripping; the workbook's own
spelling is echoed back so it can be pasted into `--sheet`.

The sentences are the same at both doors, spelling included. A per-surface variant would be a second
thing to test and would tell a Studio user nothing the CLI user is not told: `--sheet` is what the
terminal calls it, `sheet` is what the multipart field is called, and `docs/cli.md` plus the
published OpenAPI body name both. One sentence, one meaning, two places to read it.

### 2. Formula cells: stored values, and a refusal only where the import needs the cell

`load_workbook(..., data_only=True)` hands back the cached result when the file carries one and
`None` when it does not — indistinguishable from a genuinely empty cell. So the workbook may be
opened a second time (`data_only=False`, where a formula comes back as its `=SUM(A1:A2)` text) to
find out what an empty cell actually was. It is opened that way **only when the first pass left a
cell empty in a row that has other content**: an uncached formula always reads as empty, so a
workbook with no empty cell in any data row has nothing to investigate, and a clean forty-row file
pays one parse instead of two. When the second pass does run, only the coordinates that came back
empty are consulted.

| Cell | What it holds | What happens |
|---|---|---|
| statement, `importance`, `satisfaction` | a cached value | read as that value; nothing says it was ever a formula |
| statement, `importance`, `satisfaction` | a formula with no cached value | **this row is refused**: `cell B12 is a formula with no stored value; this import reads stored values and never computes them — paste it as values and import again` |
| statement, `importance`, `satisfaction` | genuinely empty | ALH-222's own refusal — empty score is absent, empty statement is `statement is empty; nothing to file` |
| `theme`, `stage`, `step_id`, `job_id`, an ignored column | a formula with no cached value | read as empty, plus one file-level warning: `3 optional cells hold a formula with no stored value (theme, stage); they were read as empty` |

The split is deliberate: a score that silently disappears is a lie about the research, and a note
that silently disappears is a filing detail the person can fix from the report. Refusing a row for
an uncached formula *anywhere* would cost good rows over a blank theme cell, which is ALH-222's
"one bad row does not cost the other thirty-nine" rule pointing the other way.

No formula is ever evaluated. `=SUM(` is never asked what it means.

### 3. Values become text the way a CSV would have carried them

The reader's job ends where the CSV reader's ends: it produces `(line number, [cells])` and the
existing header, synonym and column rules decide everything else.

- `7.0` → `"7"`, `7.5` → `"7.5"` — the shape `_number` and a spreadsheet person both expect, so
  the same row parses the same from either format.
- `None` and an empty cell → `""`.
- text and a datetime → their `str()`. A date in the `importance` column is refused by `_number`
  with `importance must be a number, got "2026-11-04 00:00:00"`, which is honest and needs no new
  rule.
- merged cells: the value lives in the top-left cell and the rest read empty. Nothing here
  re-spreads them; ALH-222's rule that a cell is read as it is, stands.

### 4. The line number is the row the person sees in their spreadsheet app

`csv.reader.line_num` already gives physical lines for the CSV door. The workbook door yields the
sheet's own row number, so an XLSX refusal says `line 12` because row 12 is where Excel shows it,
and the header row is row 1 in both formats. Blank rows keep their number while being skipped. The
equivalence test asserts the two doors refuse the *same numbers*.

### 5. The optional dependency, and where the guard lives

`packages/core/pyproject.toml` gains:

```toml
[project.optional-dependencies]
xlsx = ["openpyxl>=3.1"]
```

and the root `[dependency-groups] dev` gains a pinned `openpyxl`, so the suite that exercises the
present path installs it from the lock and no test reaches the network. `openpyxl` is imported
**inside** the reader function, under a guard, which is what makes the extra optional in every
environment — a module-level import would make `agentic_odi_core` unimportable without it.

`XlsxExtraMissingError(ValidationError)` says, verbatim:

> `reading a .xlsx needs the optional xlsx extra: pip install 'agentic-odi-core[xlsx]' — or save
> the workbook as CSV, which this build reads without it`

The absent path is tested by `monkeypatch.setitem(sys.modules, "openpyxl", None)`, which makes the
guarded import raise, so the case needs no uninstall and no network.

`scripts/build_binary.sh` gains `--all-extras` on its sync line, because a PyInstaller onedir
bundle cannot install an extra at runtime: a released CLI either reads workbooks or tells the
person to save CSV, and the bundle should not be the reason it says the second one.

### 6. How each door learns the format

By the name, because that is the only signal either door has and the person already speaks it.

- **CLI:** `Path(path).suffix` — `.csv` and no suffix are CSV; `.xlsx` is the workbook path;
  anything else is the existing `UnsupportedFormatError`, whose sentence names what was tried and
  points at CSV. `--sheet TEXT` is accepted and, for a CSV, refused with
  `a CSV has no sheets; --sheet is for a .xlsx workbook`.
- **Upload:** the multipart part's filename decides the same way, which means the route's `file`
  argument becomes `UploadFile` so the name is available (the handler stays a plain `def`, so
  reading it in the threadpool is as legal as the `asyncio.run` bridge already in there), plus a
  `sheet: str = Form("")`.
- **The loop never learns the format.** Parsing finishes before `import_outcomes` is called, so
  the MCP branch still drives exactly the tools ALH-222 drove and the server knows nothing about
  workbooks.

### 7. What the parser becomes, so the validator stays one thing

`parse_outcome_table` keeps its name and signature, plus `sheet: str | None = None`, and grows a
dispatch on the normalised `fmt`. Its body splits at the one place the formats genuinely differ —
where the rows come from:

```
read_rows(source)      →  TableLines  (csv.reader + line_num)
read_xlsx_rows(source) →  TableLines  (openpyxl, one or two loads)
      ↓
_build_rows(table)     →  ParsedTable  (header, synonyms, ignored columns, _number, problems)
```

`TableLines` is what the two formats really have to agree on:

```python
@dataclass(frozen=True)
class TableLines:
    #: (sheet or file row number, cells as text)
    lines: list[tuple[int, list[str]]]
    #: row number -> 0-based columns that held a formula with no stored value
    formula_cells: dict[int, list[int]] = field(default_factory=dict)
```

The reader answers *"is this cell a formula with no stored value?"* and nothing else, because only
`_build_rows` knows whether that column is `importance` (a refusal) or `theme` (a warning). A third
format is refused before either reader runs, and its `UnsupportedFormatError` — which ALH-222 raised
on a door no surface could reach — now has to subclass core `ValidationError` rather than plain
`OdiError`, because the upload *can* reach it by filename and a wrong suffix is a bad request, not a
server fault (`error_status()` sends an unknown `OdiError` to 500).

`_build_rows` is ALH-222's loop moved, unchanged: same header rules, same synonym refusal, same
`_number`, same blank-skip, same `ImportRow`. It gains only the line number it is handed rather
than the one the reader happens to be on. `_parsed_problems` and `ParsedTable.problems` keep their
meaning: a file-level problem, reported as the one refusal at line 1.

`ParsedTable` gains `warnings: list[str]`, which `import_outcomes` puts **before** its own
duplicate-statement warnings: the file's own condition belongs ahead of what the store knew about
it. Nothing else in the report changes, so both doors' renderers and the ALH-222 cross-door
equality test keep passing without edit.

## The report

Unchanged in shape, and that is the deliverable. A workbook run reads exactly like:

```
Would create 37 outcome(s); 3 refused.
line  statement                              reason
9     Reduce the time to…                    importance must be between 1.0 and 10.0
12    Close the invoice faster               cell B12 is a formula with no stored value; …
18    Minimize the time to approve…          Outcome statement does not match the ODI format …
theme "Retention" matches no theme on this job, so those rows were created unfiled (lines 8, 10, 11)
column "opportunity_score" ignored: opportunity is computed from the two scores, never entered
3 optional cells hold a formula with no stored value (theme, stage); they were read as empty
```

with a sheet problem answering before any of that (`Error: this workbook has rows in 3 sheets …`,
exit 1, nothing written) and a missing extra answering with the install sentence instead of a
traceback. `--json` carries the same body as ALH-222's.

## What the builder decides

- Whether the workbook fixtures are committed bytes or generated in-test. Preference: generated —
  a 40-row `.xlsx` in git is unreadable in review and drifts from its CSV twin silently.
- The exact openpyxl call shape (`iter_rows(values_only=True)` plus a coordinate walk for the
  second read) — whichever reads the two passes without a nested loop per cell.
- Whether `XlsxExtraMissingError` and `SheetSelectionError` share one class or two. Two is clearer
  in the CLI's exit message; both subclass core `ValidationError` for the status mapping.
- How many workbook-shaped cases go in the shared fixture helper versus inline in one test. Keep
  the helper small: it exists so a test can state what a file contains, not to become a spreadsheet
  library.

## Test fixtures the acceptance criteria demand

The issue names four, and each one is a test with a claim, not a smoke check:

1. **Equivalence.** A workbook built from `packages/core/tests/fixtures/outcomes_mixed_40.csv` and
   that CSV, run against the same seeded job, report the same `created`, `refused`,
   `unmatched_themes`, `ambiguous_themes` and `warnings`, and the same stored rows. Generated from
   the CSV so the two cannot drift.
2. **Extra absent.** With `openpyxl` blocked from importing, both doors name the install path and
   point at CSV: the CLI exits 1 with the sentence, the upload answers the 400 envelope — no
   traceback, no report, nothing written, no network.
3. **Never a guess, never a computation.** Two non-empty sheets refuse and name them; `--sheet`
   picks the right one; an uncached formula in `importance` refuses its row naming `B12`; an
   uncached formula in `theme` warns and writes.
4. **A dry run writes nothing and a bad row does not abort the run**, asserted through the workbook
   path rather than assumed from the CSV one.

Plus: unreadable workbook bytes → the format refusal naming the file; blank rows keep sheet row
numbers; `7.0` reads as `7`; a CSV handed `--sheet Backlog` is refused.
