# ALH-222 · M2-04.1 — Import CSV Outcomes: Design

**Linear:** ALH-222 · M2-04.1 "Import CSV outcomes with row-level validation and preview"
**Repo:** `alehar9320/agentic-odi`, workspace `shrimpfish`
**Date:** 2026-11-03
**Status:** ready for review. The three readiness blockers named in the issue are answered below and marked as my calls, not as something you agreed to; strike any of them and the shape changes.

## Intent and the why

A person doing job mapping in a spreadsheet today has one path into the store: N calls to
`odi desired-outcomes add`, each of which demands both scores and a statement, and each of
which either succeeds or dies in isolation. Their research is tabular — 40 rows of needs
statements pulled out of an interview transcript, some of them scored, some not, a theme
column they typed by hand. What they want is to hand that file over and be told, row by
row, what will be written and what will not and why, before anything is written.

So this increment is: read a CSV, validate every row against the same rules a single `add`
would face, and report the whole run — created, refused with the original line number and
the service's own sentence, themes that could not be matched. The same parse and the same
report behind the CLI and the Studio upload endpoint, so a person cannot get two answers
depending on which door they used.

The point is not bulk. The point is that a spreadsheet arrives dirty and the store must stay
clean without the importer guessing.

## Goals

- `odi desired-outcomes import <path> --job-id <id> [--dry-run] [--json]` parses a CSV and
  runs the import.
- `POST /api/outcomes/import` accepts the same file as multipart and returns the same report.
- One shared parser and one shared report in `packages/core`, used by both surfaces.
- Row-level validation: one bad row is refused and named; the other 39 are still written.
- Preview: `--dry-run` / `dry_run=true` produces the same report as the write run on an
  unchanged file, and writes no entities and no events.
- Statement validation is never bypassed and never repaired: `evaluate_outcome_statement`
  decides, and the row is refused with its verdict.

## Non-goals

- XLSX. It is the sibling increment (ALH-223) and reuses this parser's output shape; nothing
  here anticipates its reading code beyond the `fmt` argument.
- Theme creation. An unmatched theme name is reported, never minted.
- Deduplication. A second import of the same file creates the same outcomes again. It warns
  that it did, and it does not skip, merge, or refuse them for being repeats.
- Tags, evidence, customer outcomes, and the Studio drop-zone UI.
- Any change to the MCP server's tool surface. No new tool, no changed signature.

## Anti-goals

- An import that "fixes" a row: trimming a statement into a shape that passes, defaulting a
  missing score to zero, picking the closest theme name. Every one of those turns a person's
  research into something they did not write.
- A whole-file failure. One `importance=11` must not cost 39 good rows.
- A report that is a success count. `37 created` without the three refusals is worthless,
  because the three refusals are the reason the person ran a preview.
- A silently ignored column. A file with `importance_n` and `satisfaction_n` loses those
  numbers; the report must say they were lost.

## Constraints

- Domain model: outcomes belong to a Job (`job_id`), optionally to a Step (`step_id`), and are
  filed under Themes by id. `Outcome` has `importance`, `satisfaction`, `opportunity_score`,
  `claim_check`, `theme_ids`, `tags`, `study_id`. There is **no** `importance_n` or
  `satisfaction_n` field anywhere in the codebase, and this increment does not add one.
- `OdiService.add_outcome` (services.py:565) is the only writer: it raises `JobNotFoundError`,
  `StepNotFoundError`, `ValueOutOfRangeError` ("importance must be between 1.0 and 10.0"),
  `InvalidOutcomeStatementError`, or `ClaimCheckError`.
- Core modules must be listed in `tests/test_architecture.py::CORE_LAYERS` and in the layer
  table in `docs/architecture/README.md` in the same change. The new module is
  **methodology**, next to `services.py`, not domain: it calls `manual_claim_check()` and
  drives writes, and the domain group may import neither methodology nor persistence
  (`docs/architecture/README.md:129`). Its `target` protocol keeps it free of `ODIService` so
  the MCP adapters can satisfy it.
- Studio API responses must appear in the committed `apps/studio/openapi.json` and
  `src/api/schema.d.ts`, regenerated rather than hand-edited.
- `docs/cli.md` must document the new command: `website/tests/test_generated.py::test_the_cli_reference_mentions_every_registered_command`
  fails the build when the hand-written reference falls behind the CLI's registered commands.
- The header synonyms the issue calls "documented" exist nowhere in this repo today (no
  `statement`/`outcome`/`need` table in `docs/`, no parser that reads them). This document is
  where they get defined, and `docs/cli.md` is where they get published.
- Website weight guard: the docs/mcp reference page has a byte ceiling that has been moved
  repeatedly; this increment adds no tool, so it must not move again.
- Stdlib `csv` only. No new third-party parsing library.
- `python-multipart` is declared explicitly in `apps/studio-api/pyproject.toml`. FastAPI needs
  it for `UploadFile`/`Form`, and it appears in `uv.lock` today only transitively through `mcp`
  and `fastmcp` — depending on something whose presence you are borrowing from a neighbour is
  not a contract. No other new dependency, and no version bump: the lock already resolves it.

## The decisions the readiness blockers asked for

The issue says: *"define target-job selection, duplicate header synonyms and ambiguous exact
theme names before coding; neither CLI nor upload currently specifies the target-job
contract."* Here they are.

### 1. Target job

The target job is **the run's parameter, never a row's choice.**

- CLI: `--job-id` is required, exactly like `add`, `list`, and `export`.
- Upload: multipart field `job_id`, required alongside `file`.
- A `job_id` column in the file is read and compared, not obeyed. A row whose `job_id` cell
  disagrees with the run's target is refused: *"row 12 says job X, this import targets job Y;
  import against job X or drop the column."* That is the whole reason the cell is read — to
  catch a file exported from one job and imported into another, which would otherwise
  relocate research quietly.
- A `step_id` column **is** obeyed, when present and non-empty: it is checked through the
  same `get_step` the service uses, so an unknown id refuses the row with
  `StepNotFoundError`'s own sentence. Obeying it is what makes an `export` → edit → `import`
  round trip land on the same rows it left.
- An unknown `--job-id` / `job_id` field is a **request** mistake, not a row mistake, and is
  answered the way every other surface answers it: CLI prints `JobNotFoundError`'s sentence
  and exits 1; the upload endpoint returns the 404 `_as_http_error` already gives for
  `POST /outcomes`. It is never dressed up as a report with one refusal, because there is no
  file to talk about yet.

### 2. Header synonyms and duplicates

Canonical headers are the `export` field names, so a file this tool wrote is a file this tool
reads: `statement`, `importance`, `satisfaction`, `step_id`, `job_id`, plus the import-only
`theme` and `stage`. Synonyms for the statement column, accepted case-insensitively after
trimming: `outcome`, `need`.

The round trip is therefore statement, scores, and step — not filing. `export` writes
`EXPORT_FIELDS` (`id, job_id, step_id, statement, importance, satisfaction, opportunity_score`)
and emits no `theme` or `stage` column, so an `export` → `import` cycle does not carry theme
filing across; widening `export` is out of scope here and the round-trip test asserts the
narrow claim rather than a round trip that quietly drops a person's themes.

- Two synonyms carrying **different non-empty values** in one header (`statement` and `need`)
  is ambiguous, so the header mapping refuses at parse time — before any row is read — with
  the columns named. Choosing one by declared priority would be guessing at a person's intent
  with their whole file on the line.
- Two spellings of the same column with the same meaning (`outcome` and `need`) map to one
  and are not an error.
- Any header that is neither canonical nor synonym is reported in `unknown_columns` with what
  was done with it (ignored) and is **not** fatal. A spreadsheet carries a `Notes` column;
  the import should still work, and should say what it dropped.
- `id` and `opportunity_score` are known-and-ignored, reported as such: an exported file has
  them, an import must not act on either. `importance_n` and `satisfaction_n` are parsed into
  the row (the issue's row shape names them) and reported as ignored, because `Outcome` has
  nowhere to store a count. They are never coerced into the score fields and never zeroed.

### 3. Ambiguous exact theme names

A `theme` cell is matched **by exact, case-sensitive name** against the themes visible to the
target job: that job's own themes plus the workspace-wide ones (`job_id is None`). No fuzzy
matching, no substring, no creation.

- **One match** → the created outcome is filed under it via the existing
  `assign_theme([outcome_id], theme_id)`.
- **No match** → the outcome is still created (the statement is the research; the theme is
  filing), and the name appears in `unmatched_themes` with the line numbers that used it.
- **More than one match** — the same name existing as both a job theme and a workspace theme —
  → the outcome is created, left unfiled, and the name appears in `ambiguous_themes` with the
  candidate ids. Never picked silently; the person has to rename one of them or target the
  theme, and the report tells them which two.

A cell naming several themes (`Onboarding; Activation`) is out of scope: one theme per cell,
documented, and a cell containing a separator that matches nothing arrives in
`unmatched_themes` verbatim, which is the honest outcome rather than a silent split.

### 4. A score with no questions behind it (what the issue did not ask, and the repo already answered)

The two doors do not agree today, and the importer has to pick which one is right:

- `OdiService.add_outcome` permits `claim_check=None` alongside two scores.
- The MCP `add_outcome` tool (mcp_server.py:185) **refuses** it: *"add_outcome cannot record a
  score without a claim_check… To record an outcome before asking, omit importance and
  satisfaction."*
- Both existing by-hand capture paths bridge the gap the same way: the CLI's `add`
  (desired_outcomes.py:83) and `POST /outcomes` (router.py:813) attach `manual_claim_check()`
  when no check was supplied — a skip carrying the reason "Score entered by hand; no customer
  questions were asked."

A spreadsheet is a by-hand path in exactly that sense: the numbers came from a file, not an
interview. So the importer does what the other two capture paths do — a row with either score
gets `manual_claim_check()`, a row with no scores gets nothing. This is not stylistic: it is
what makes an import behave identically through the local and MCP doors, since the MCP door
rejects a score with no check. It is also why no `--claim-check` option exists on `import`: a
transcript does not become an interview by being in a file, and an option that lets a person
paste a claim check for 40 rows at once would let a fabricated interrogation look like a
conducted one.

### 5. The stage column

A `stage` cell must name a `JobStage` value (`define`, `locate`, …). An unrecognised value is
refused with the same sentence `query.py:53` uses for the same mistake ("Unknown stage: …").
A recognised one resolves to the target job's step whose `stage` matches; zero steps is a
refusal (nothing to attach to), more than one is a refusal naming the candidate step ids,
for the same reason an ambiguous theme is one — a spreadsheet does not get to choose.

### 6. One loop, three writers, no new tool

Both surfaces call one core function, `import_outcomes(rows, target, job_id=…, dry_run=…)`,
where `target` is a small protocol with the five things the loop needs — three reads that
happen once, before any row is touched, and two writes that happen per row:

| | |
|---|---|
| `themes()` | the job's themes plus the workspace's, for name resolution |
| `steps()` | the job's steps, for `stage` resolution |
| `existing_statements()` | the job's current statements, for the duplicate warning |
| `add_outcome(row) -> outcome_id` | write one row |
| `assign_theme(outcome_ids, theme_id)` | file many rows under one theme at once |

The three reads are batched because they are lookups against a stable state, and the theme
write is batched because `assign_theme` already takes a list: a 40-row file with 6 matched
themes costs 40 outcome writes and 6 filings, not 80 calls. That matters on the remote door,
where every call is a session.

Three `target` implementations, one per existing routing path:

- **Direct** (Studio local mode, and the CLI's default `local` backend): the `ODIService`.
- **MCP from the CLI**: the CLI's `run_tool`, which is how `add`, `bulk` and `search` already
  reach either backend — the import command does not choose a backend, and gains nothing by
  starting to.
- **MCP from the Studio API**: an adapter over `call_mcp_tool` for `add_outcome` and
  `assign_theme`.

No new MCP tool and no server change: the issue carries no `area/mcp` label because nothing in
the contract moves.

**A refusal and an outage are different things, and the loop says them differently.** The
Studio adapter classifies on the error code `call_mcp_tool` already distinguishes:
`MCP_TOOL_FAILED` means the tool ran and refused, so the row is refused with the tool's own
sentence; `MCP_UNREACHABLE` means the server is gone, so the run **stops**, the rows already
written stay written and stay listed in `created`, and the report carries
`aborted: {line, reason}`. Turning a dead server into 40 refusals would be the single most
misleading thing this feature could do. The CLI's remote path does the same with its own
transport error.

**The shared local handler has to be corrected, and this is the one pre-existing bug this
increment owns.** `LocalBackend._add_outcome` (backend.py:240) does
`float(args["importance"])` and `float(args["satisfaction"])` on required keys, while the tool
contract declares both optional and the service accepts `None`. So an unscored row — the
common row in a research file — raises `KeyError` through the CLI's default backend instead of
creating an outcome. The fix is `.get()` with a `None` guard, in the shared handler, so `add`
keeps its behavior (it always passes both) and the import path stops crashing. Its
`_VALUE_RANGE_ERROR` sentence stays exactly as it is: three tests across three apps pin it and
it mirrors the tool's own text. The importer never depends on it, because the importer
pre-validates each row against the bounds itself (below) and quotes whatever sentence arrives.

**Preview is honest because the loop validates before it writes, with the service's own
rules.** Per row: `evaluate_outcome_statement`, the 1..10 bounds per field, the stage value
against `JobStage`, the theme name, the step id, the job id cross-check. A dry run reports
those refusals and never calls a writer; a write run reports the same refusals and *additionally*
folds anything the writer rejects into a refusal with the writer's own message, inside a
per-row `try`. So the preview and the write agree on an unchanged file, and no row can cost
the other 39 their write.

### 7. Duplicate warning

There is nothing in core to inherit here — the search's text match is a lowercase substring
test, which would call "Minimize the time to deploy" a repeat of "deploy" — so the import
defines its own rule and it is a strict one: **equal after casefolding and collapsing runs of
whitespace to one space.** Not fuzzy, not substring, not embedding.

A row is checked against the target job's existing outcomes **and against earlier rows of the
same file** (a 40-row file that pastes the same need twice is a file the person wants to know
about, and the second row is not the store's problem yet). A match does not stop the write —
no deduplication — it adds a line to `warnings`: *"row 3 repeats '…' already filed as outcome
abc-123; this import will create a second one"*, naming which. `--dry-run` prints the same
warning, which is the point of running a preview before a repeat import.

### 8. There is no undo, and that is the answer, not an oversight

`bulk` ships an undo token because it rewrites rows that already exist; an import only adds
rows, and every row it added is printed with its id. The way back is the delete command that
already exists, one id at a time: `odi desired-outcomes delete <id>`. A run token would mean a
new stored artifact and a new MCP tool, which the issue's scope rules out. The CLI's human
output says this after a write run — *"to take this back, delete these ids"* — so a person is
not left hunting for an `undo` subcommand that does not exist.

## The report

One shape, shared by both doors, in this order:

| field | meaning |
|---|---|
| `job_id`, `dry_run` | what was targeted, and whether anything was written |
| `created` | per row: `line`, `statement`, `importance`, `satisfaction`, `outcome_id` (null in a dry run) |
| `refused` | per row: `line`, `statement`, `reason` — a service sentence, never a paraphrase |
| `unmatched_themes` | name → lines |
| `ambiguous_themes` | name → candidate theme ids → lines |
| `unknown_columns` | header → what happened to it |
| `ignored_columns` | header → why nothing was done with it (`importance_n`, `opportunity_score`, …) |
| `warnings` | duplicate rows, and any other thing a person should know before they trust this run |
| `aborted` | null, or `{line, reason}` when the server went away mid-run |

`line` is the **physical line of the file**, from `csv.reader.line_num`, with the header on
line 1 — so every number a person reads in a report is a number they can find in their
spreadsheet app, and a file whose very first line is wrong reports line 1.

Counts are derived, not stored: `created`/`refused` lengths are the "37 created / 3 refused"
a person reads. CLI human output prints the summary line, then the refusals with line
numbers, then the theme and column notes; `--json` prints the report object as it is. The
upload endpoint returns the same object, so the Studio board and the terminal disagree on
nothing.

A file that cannot be parsed at all (no header row, no `statement`/`outcome`/`need` column,
an empty file, two conflicting statement headers) yields a report with **zero rows and one
refusal at line 1** carrying the parse error, not an HTTP 500 or a traceback — and a
**200**, because a well-formed answer to a badly-formed file is an answer, not an error. The
errors that are not the file's fault keep the status the rest of the router gives them: 404
for an unknown `job_id`, 422 for a missing `file` or `job_id` field. Same for a non-CSV body:
`fmt` is `"csv"` and anything else is refused with that word.

## What the builder decides

- Name of the dataclasses and helpers inside `outcome_import.py`, so long as the module is
  methodology, the two public functions keep the shapes the issue names, and the architecture
  test and the layer table move with it.
- Exact sentence wording, except where the issue or the existing service fixes it (a refusal
  quoting the service keeps the service's words; `Unknown stage: …` is `query.py`'s).
- Whether the CLI reader is a `pathlib` read or an open file handle, and how it decodes
  (a UTF-8 read with `newline=""` is what `csv` wants).
- Whether the Studio upload test suite uses `httpx` multipart or Starlette's own client
  helpers — whatever the repo already uses for its router tests.

## Test fixtures the acceptance criteria demand

- A 40-row CSV with exactly three broken rows → 37 created, 3 refused, each refusal naming
  its original line and carrying the reason verbatim; one of the three is `importance=11` and
  does not abort the rest.
- The same file run `--dry-run` twice → identical report, zero rows in the store, zero events.
- One fixture file used by both the CLI test and the upload test, asserting the same report —
  that is the shared-parser criterion, and it is the test that fails first if someone forks
  the loop.
- A file with only broken rows, an empty file, a file with no `statement` column, a file with
  a `statement` and a `need` column that disagree → each an actionable report, none a crash.
- Blank score cells → the outcome has `importance=None`, not `0`.
- An export → import round trip through the same job.
- A theme name that exists twice, and one that exists nowhere.
- An unscored row written through the CLI's default local backend — the fixture that fails
  before the `LocalBackend._add_outcome` correction, and passes after it.
- A remote run whose server stops answering at row 20: the report shows 19 created, no
  refusals, and `aborted`, and does not show 20 invented failures.
- A row with a score, imported through the MCP door: it is written, because the importer
  attached `manual_claim_check()` — this is the fixture that keeps the two doors equal.
