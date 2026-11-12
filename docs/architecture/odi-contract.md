# The ODI contract

This document is the reference for what Outcome-Driven Innovation means *in this
codebase*: the rules, the format, the score, the Job Map, and — the part that
matters — where each rule is enforced. The methodology itself is defined by
Anthony W. Ulwick's *What is Outcome-Driven Innovation?* (committed under
`docs/reference/`); this page records how the implementation encodes it.

## What it is

ODI treats a product decision as a claim about a customer's job, and a claim is
only useful if it can be measured and argued with. The contract has five parts:

1. **A Job-to-be-Done** — a stable functional goal, not a product or a feature.
2. **Desired outcomes** — the metrics a customer uses to judge success, written
   as `[Direction] + [Unit of Measure] + [Object of Control] + [Contextual Clarifier]`.
3. **Two scores per outcome** — importance and satisfaction, both on a 1–10
   scale. Both are optional: an unscored outcome is a legal record.
4. **An opportunity score** — `importance + max(importance − satisfaction, 0)`,
   with **> 10 underserved**, **= 10 served**, **< 10 overserved**.
5. **A claim check on a score** — a scored outcome carries the questions behind
   the number: what was `asked`, the `answers` that came back, and any `skips`
   with a reason. `verified` is derived from the answers, never typed in.
6. **The questions come first** — three of them, put to the person, before any
   number is written. The prompts say so, the card shows them, and
   `assert_asked_before_scoring` judges a transcript by that order.

Everything else (segments, strategy, the Job Map) is downstream of those six.

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
| A rating a customer did not give is never substituted | `ODIService.update_outcome` (`services.py:416-421`), `segment_verdict` (`segmentation.py:43-53`), `SQLiteRepository` opening a store (`sqlite_repository.py`) | An outcome missing either rating keeps `opportunity_score = None`, and opening a store appends no event and changes no number: unscored stays unscored across reloads and processes, and a segment with an unscored outcome gets no verdict |
| A score is compared as stored and shown rounded | `isUnderserved` and `formatOpportunityScore` (`apps/studio/src/lib/odi.ts`); `OpportunityLandscape` sorts and filters on `outcome.opportunity_score` | Rounding happens once, where a score becomes text. Two outcomes that both print `13.0` still have an order, so sorting, filtering and averaging never read the formatted string |
| A service's reported scores match the shared arithmetic | `assert_outcome_scores_match` (`evaluation.py`) judged against `packages/core/tests/fixtures/opportunity-score.json` | A service that scores through `compute_opportunity_score` passes; one that computes its own fails with the outcome id and both values named. An unscored outcome is allowed |
| A score carries the questions behind it | `ClaimCheck` on `Outcome` (`models.py`), `require_claim_check` and `ODIService.add_outcome` (`services.py`), the `add_outcome` MCP tool (`apps/mcp-server/.../mcp_server.py`) | The MCP tool refuses a score with no `claim_check`; the check records `asked`/`answers`/`skips` and derives `verified`. Unscored outcomes stay legal; a skip without a reason is rejected |
| The questions reach the person before the number | `assert_asked_before_scoring` (`evaluation.py`) over an interview transcript; the Studio system prompt (`apps/studio-api/.../studio/chat.py`), the ODI guidelines (`messages.py`) and the `add_outcome` description | The prompts put three questions before any score and forbid answering them yourself. The harness refuses a transcript that scores first, and any answer that is not in a customer turn before the score; an unscored outcome needs no interview |
| Outcome statements follow the ODI format | `evaluate_outcome_statement` (`evaluation.py:84-147`) via `ODIService.add_outcome(validate_statement=True)` | Invalid statements raise `InvalidOutcomeStatementError` with issues and suggestions |
| Statements can be checked before writing | `evaluate_outcome` MCP tool, `odi desired-outcomes evaluate`, `odi evaluate` | Returns `valid`, direction, unit, object, clarifier, issues, suggestions |
| The eight Universal Job Map stages are one constant | `JOB_STAGE_ORDER` and `job_stage_catalog()` (`models.py`), generated to `apps/studio/src/domain/jobStages.ts` | `scripts/gen_job_stages.py` regenerates the file; `tests/scripts/test_gen_job_stages.py` fails if it is stale |
| Steps occupy a stage | `Step.stage_index` (`ge=1, le=8`) and `Step.stage` (`JobStage`) | Position is optional but bounded when present |
| A score above 10 is "underserved" | `UNDERSERVED_SCORE` (`evaluation.py:13`) and `isUnderserved` with `UNDERSERVED_THRESHOLD` (`apps/studio/src/lib/odi.ts:9`) | `classify_opportunity` buckets strictly above the line, so exactly 10 reads as served; `tests/test_underserved_threshold_parity.py` fails if the Python and TypeScript numbers ever disagree |
| Every adapter exposes the same tools | `ToolName` / `TOOL_SPECS` in `contract.py` | `tests/contract/test_mcp_contract.py` and `test_cli_contract.py` fail on drift |
| A record shown in full is only ever what was stored | `DETAIL_FIELDS` and the honesty sentences (`apps/studio/src/components/records/RecordDetail.tsx`) | The detail names the fields each kind really has and nothing else — `Outcome.telemetry` stays unshown because it has no defined shape — and says in words that no author or timestamp exists. A missing value renders `—`, an unscored outcome `unscored`; `Unknown`, `N/A`, and a guessed date are never rendered |

The statement checker is deliberately mechanical: it requires a leading
`Minimize`/`Maximize`, a known unit of measure (or a digit), an object after
"the", a context marker (`when`, `while`, `before`, `after`, `during`, `if`,
`as`), at least six words, at most 200 characters, no vague terms (`better`,
`improve`, `optimize`, `faster`, `easier`), and no solution nouns
(`notification`, `dashboard`, `button`, …). It returns issues and suggestions
rather than a bare boolean so the agent can repair a statement in the same turn.

## Outcome statement rubric

The following table lists every rule enforced by `evaluate_outcome_statement`,
published by `outcome_rubric()`, and checked per rule in the `checks` array
returned by the evaluator. The rubric is derived from the validator constants,
so a constant edit cannot drift from the published rules.

| Rule ID | Label | Check | Fails when | Example (failing) |
|---|---|---|---|---|
| `direction` | Leading direction | Statement starts with "Minimize" or "Maximize" | Missing or wrong leading word | `The time it takes to onboard a customer when they sign up` |
| `unit_of_measure` | Unit of measure | Contains a known unit (time, cost, number, frequency, rate, percentage, steps, attempts, or a digit) | No unit and no digit | `Minimize the onboarding when they sign up` |
| `object_of_control` | Object of control | Names an object after "the" | No " the " in statement | `Minimize time to onboard a customer when they sign up` |
| `contextual_clarifier` | Contextual clarifier | Contains a context marker (when, while, before, after, during, if, as) | No context marker | `Minimize the time it takes to onboard a customer` |
| `min_words` | Minimum length | At least 6 words | Fewer than 6 words | `Minimize the time` |
| `max_chars` | Maximum length | At most 200 characters | More than 200 characters | (long statement exceeding 200 chars) |
| `vague_terms` | No vague terms | No vague terms (better, improve, optimize, faster, easier) | Any vague term present | `Make onboarding faster when they sign up` |
| `solution_nouns` | No solution nouns | No solution nouns (notification, dashboard, button, feature, screen, email, workflow, integration, report, toggle) | Any solution noun present | `I want a notification when onboarding finishes` |

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
