# The ODI contract

This document is the reference for what Outcome-Driven Innovation means *in this
codebase*: the rules, the format, the score, the Job Map, and — the part that
matters — where each rule is enforced. The methodology itself is defined by
Anthony W. Ulwick's *What is Outcome-Driven Innovation?* (committed under
`docs/reference/`); this page records how the implementation encodes it.

## What it is

ODI treats a product decision as a claim about a customer's job, and a claim is
only useful if it can be measured and argued with. The contract has four parts:

1. **A Job-to-be-Done** — a stable functional goal, not a product or a feature.
2. **Desired outcomes** — the metrics a customer uses to judge success, written
   as `[Direction] + [Unit of Measure] + [Object of Control] + [Contextual Clarifier]`.
3. **Two scores per outcome** — importance and satisfaction, both on a 1–10
   scale.
4. **An opportunity score** — `importance + max(importance − satisfaction, 0)`,
   with **> 10 underserved**, **= 10 served**, **< 10 overserved**.

Everything else (segments, strategy, the Job Map) is downstream of those four.

## Why it exists

Without the contract, "customer need" collapses into prose: a model can invent a
quote, a feature request becomes an outcome, and a score becomes a vibe. Encoding
the rules means the same statement, score, and stage list are checked by the
CLI, the MCP server, the Studio API, and the Studio itself, so a chat turn and a
hand-edited record cannot disagree about what a valid outcome is.

## Where each rule is enforced

| Rule | Enforced by | Behavior |
|---|---|---|
| Importance and satisfaction are 1–10 | `Outcome` fields (`packages/core/src/agentic_odi_core/models.py:116-121`) and `ODIService.add_outcome` (`services.py:411-414`) | Pydantic rejects out-of-range values; the service raises `ValueOutOfRangeError` before writing |
| Opportunity score is computed, not supplied | `compute_opportunity_score` (`models.py:85-87`), called by `add_outcome` and the SQLite update path | A caller cannot store a hand-picked score |
| Outcome statements follow the ODI format | `evaluate_outcome_statement` (`evaluation.py:84-147`) via `ODIService.add_outcome(validate_statement=True)` | Invalid statements raise `InvalidOutcomeStatementError` with issues and suggestions |
| Statements can be checked before writing | `evaluate_outcome` MCP tool, `odi desired-outcomes evaluate`, `odi evaluate` | Returns `valid`, direction, unit, object, clarifier, issues, suggestions |
| The eight Universal Job Map stages are one constant | `JOB_STAGE_ORDER` and `job_stage_catalog()` (`models.py`), generated to `apps/studio/src/domain/jobStages.ts` | `scripts/gen_job_stages.py` regenerates the file; `tests/scripts/test_gen_job_stages.py` fails if it is stale |
| Steps occupy a stage | `Step.stage_index` (`ge=1, le=8`) and `Step.stage` (`JobStage`) | Position is optional but bounded when present |
| Every adapter exposes the same tools | `ToolName` / `TOOL_SPECS` in `contract.py` | `tests/contract/test_mcp_contract.py` and `test_cli_contract.py` fail on drift |
| "No solution" is never fabricated from an un-inventoried outcome | `_solution_state` (`services.py`), `EXISTING_SOLUTION_LABELS` (`models.py`), `render_alternative_lines` (`alternatives.py`) | One three-state rule: `yes`, `no_linked_nothing`, `no_link_at_all`; the last two word differently, so "we asked and there is nothing" is never rendered as "we have not asked" |

The statement checker is deliberately mechanical: it requires a leading
`Minimize`/`Maximize`, a known unit of measure (or a digit), an object after
"the", a context marker (`when`, `while`, `before`, `after`, `during`, `if`,
`as`), at least six words, at most 200 characters, no vague terms (`better`,
`improve`, `optimize`, `faster`, `easier`), and no solution nouns
(`notification`, `dashboard`, `button`, …). It returns issues and suggestions
rather than a bare boolean so the agent can repair a statement in the same turn.

## What the alternatives were

- **Free-text outcomes judged by the model.** Rejected: the model cannot be the
  validator of its own claim, and two runs disagree. The mechanical checker is
  blunt but repeatable, and the model gets structured feedback.
- **Store the opportunity score as an input.** Rejected: it lets a stale or
  hand-picked number outlive the importance/satisfaction it came from. The score
  is always derived, and repository updates recompute it.
- **Free-string stages.** Rejected: the Job Map would drift per adapter. The
  stage list is one Python constant rendered into the Studio.
- **Demographic segmentation.** Rejected by the methodology itself: groups are
  defined by which outcomes are underserved, not by who the customer is.

## What this does not do

- It does not sample customers, estimate statistical confidence, or decide how
  many interviews are enough.
- It does not compute outcome-based segments or a strategy recommendation; those
  are downstream work ([#85](https://github.com/alehar9320/agentic-odi/issues/85)).
- It does not enforce the *behavioral* order of ODI (job before outcomes, before
  the Job Map) at the type level. The order is a prompt and guardrail rule; the
  store accepts a step without an outcome.
- It does not require every consumer of `add_outcome` to validate statements
  through a single door: the checker lives in the service, so a caller that
  constructs an `Outcome` and writes it through a repository bypasses it.
- It does not treat the score as a probability or a percentage. It is a
  comparative ranking on the Ulwick scale.
