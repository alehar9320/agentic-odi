# Interviews: quote to candidate to outcome

An interview is a source of quotes. A quote proposes candidate outcomes; a
person accepts the ones that read as real ODI statements. Nothing is written as
an Outcome until a person accepts it, so the loop never mistakes a model's
suggestion for a finding.

This guide walks the first three stages of the spine — **quote → candidate →
outcome** — and stops where the score stage begins ([Scoring and the
landscape](scoring.md)).

## What you need

- A local store. Every command here is local-first and needs no server.
- A Job to hang outcomes off. If you do not have one, `demo load` creates a
  labelled sample you can explore without doing research first.

```bash
export AGENTIC_ODI_DB=./interviews.db      # an isolated store for this walkthrough
agentic-odi demo load                      # optional: a labelled sample job
```

> `demo load` writes rows tagged `origin="demo"`. They are sample data, never
> your research, and `agentic-odi demo clear` removes only those rows.

## 1. A quote proposes candidates

`candidates extract` runs the deterministic fixture extractor over one quote and
persists what it proposes. It proposes only — it never writes an Outcome.

```bash
agentic-odi candidates extract \
  --quote-id interview-7 \
  --quote "Minimize the time it takes to onboard when a customer signs up. Minimize the number of setup errors when a customer signs up." \
  --job-id demo-job-1
```

Each line prints the candidate's status and id:

```
- [proposed] Minimize the time it takes to onboard when a customer signs up.  (…)
- [proposed] Minimize the number of setup errors when a customer signs up.  (…)
```

The extractor validates each statement against the ODI format rules. A sentence
that does not read as an outcome comes back `[rejected]`, with the reason kept
on the candidate — it is never silently dropped or rewritten.

## 2. Review what was proposed

```bash
agentic-odi candidates list --job-id demo-job-1
agentic-odi candidates list --status proposed --json
agentic-odi candidates show <candidate-id>
```

`list` filters by quote, job, or status. `show` prints one candidate with its
source quote, rationale, confidence, and the outcome it became (if accepted).

## 3. A person accepts, rejects, or merges

Acceptance is the only path that creates an Outcome. It goes through
`ODIService.add_outcome`, so the outcome validator runs and the evidence link is
recorded.

```bash
# Accept, choosing the two scores a person is responsible for.
agentic-odi candidates accept <candidate-id> --importance 9 --satisfaction 4

# Accept with an edited statement instead of the proposed wording.
agentic-odi candidates accept <candidate-id> --importance 9 --satisfaction 4 \
  --statement "Minimize the time it takes to onboard a customer when they sign up."

# Reject: the reason is required and kept.
agentic-odi candidates reject <candidate-id> --reason "names a solution, not an outcome"

# Merge: fold a near-duplicate into an existing Outcome. Creates no outcome.
agentic-odi candidates merge <candidate-id> --merged-into <outcome-id>
```

`accept` creates **exactly one** Outcome. An already-decided candidate is refused
rather than re-accepted, so a retry cannot double-write.

## Where it lands

The accepted Outcome is a normal ODI outcome with an opportunity score. Continue
with [Scoring and the landscape](scoring.md) to read the score, or
[The decision artifact](decision.md) to turn the landscape into a brief and a
decision.

```bash
agentic-odi desired-outcomes get <outcome-id>   # statement, scores, opportunity
```

## Empty and failure paths

Each of these is a normal state, and each says so rather than inventing a
finding.

- **Nothing proposed yet.** `candidates list` prints `No candidates yet.`
- **No extractable candidates.** A quote that contains no ODI statement yields
  `[rejected]` candidates with a reason; the store still holds zero outcomes.
- **A candidate is not an outcome.** Until `accept` runs, `desired-outcomes get
  <candidate-id>` reports nothing — a proposal is not a result.

## See also

- [CLI reference](cli.md) — every flag for the `candidates` group.
- [Scoring and the landscape](scoring.md) — sample size, bands, and history.
- [The decision artifact](decision.md) — brief, decision, bet, measure.
