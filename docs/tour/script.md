# The ninety-second tour

The loop in one sitting, on the labelled sample workspace: load the sample, read
the landscape, turn a quote into an accepted outcome, and render the brief that
carries its numbers. Every command below is executed by `scripts/tour.py`; a
command that cannot be executed fails the tour build.

Regenerate the committed cast and transcript with one command:

```bash
uv run python scripts/tour.py
```

The tour runs offline against a disposable store — no model, no network, and no
access to your own store. It measures its own wall-clock and fails if the
walkthrough exceeds the ninety-second budget.

## Prerequisites

A clean checkout with the CLI installed (`uv run` resolves the workspace). The
tour sets `AGENTIC_ODI_DB` to a fresh temporary file, so nothing it does touches
a store you use.

## The walkthrough

1. `agentic-odi demo load` — load the labelled sample workspace, tagged `origin="demo"`.
2. `agentic-odi jobs list` — the sample job is there to explore.
3. `agentic-odi summary demo-job-1 --top 3` — read the landscape and its biggest opportunities.
4. `agentic-odi candidates extract --quote-id tour-q1 --quote "Minimize the time it takes to onboard when a customer signs up." --job-id demo-job-1` — a quote proposes a candidate outcome; nothing is accepted yet.
5. `agentic-odi candidates list --job-id demo-job-1 --status proposed` — review what was proposed.
6. `agentic-odi candidates accept {candidate_id} --importance 9 --satisfaction 4` — a person accepts; the candidate becomes exactly one Outcome.
7. `agentic-odi brief {outcome_id}` — render the brief; every figure carries the words that explain its number.
8. `agentic-odi score 8 2` — the opportunity formula, on its own.
9. `agentic-odi store` — the store's schema version, read through the same path every command uses.
10. `agentic-odi spine` — which stages of the loop this build implements.

## Substitutions

`{candidate_id}` and `{outcome_id}` are the only substitutions. The tour
resolves them from the id the previous step printed — a candidate id from the
`extract` line, and the outcome id from the `accept` reply — so the transcript
walks the real loop rather than a replayed fixture.

## What is not here

The Studio screenshots and their embeds are a separate slice
([ALH-236](https://linear.app/alhase-personal/issue/ALH-236/m5-072-capture-the-studio-tour-and-keep-embeds-current));
this script is the terminal walkthrough. `python scripts/dev.py` starts the
interactive MCP and Studio surfaces; it is not part of this offline cast.
