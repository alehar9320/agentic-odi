# Scoring and the landscape

An ODI outcome carries two numbers a person is responsible for — **importance**
and **satisfaction**, both 1–10 — and one the product computes: the opportunity
score.

```
opportunity_score = importance + max(importance - satisfaction, 0)
```

This guide covers the score stage: computing it, reading it back with its basis,
and the honest states a thin or missing score produces. It continues from
[Interviews: quote to candidate to outcome](interviews.md) and leads into [The
decision artifact](decision.md).

## 1. Compute a score

```bash
agentic-odi score 8 2          # → Opportunity score: 14.00
```

`score` applies the formula directly. The same computation is what `accept`
stores, so the number you see here is the number the outcome carries.

## 2. Read a score with its basis

Every figure the product shows travels with a **basis** — the words that explain
where it came from. The score stage returns the sample and its basis:

```bash
agentic-odi desired-outcomes get <outcome-id>
```

```
id            <outcome-id>
job_id        demo-job-1
statement     Minimize the time it takes to onboard when a customer signs up.
importance    9.00
satisfaction  4.00
opportunity   14.00
```

Via the MCP tool surface (`get_outcome_score`), the same stage also reports
`sample_size`. It is `None` when unknown — **unknown is not zero**. A score from
one quote and a score from a hundred interviews are not the same claim, and the
product never invents the difference.

## 3. Read the landscape

```bash
agentic-odi summary <job-id>
agentic-odi summary <job-id> --top 3
agentic-odi summary <job-id> --json
```

`summary` ranks a Job's outcomes and lists the underserved ones (score above 10)
in descending order:

```
job          Sync environment secrets across microservices (demo-job-1)
job map      8 of 8 phases
outcomes     40 captured, 3 underserved

Biggest opportunities:
statement                                                     score
------------------------------------------------------------  -----
Minimize the time it takes to test a rotation against the C…  18.00
Minimize the time it takes to take a new secret safely whe…   17.00
Minimize the time it takes to verify permissions before a d…  16.00
```

`--top` caps that list; `--json` returns the same data for a script.

## 4. Export the scored set

```bash
agentic-odi desired-outcomes export --job-id <job-id> --format csv > outcomes.csv
agentic-odi desired-outcomes export --job-id <job-id> --format json | jq '.[].opportunity_score'
```

`export` writes to stdout only — CSV has one row per outcome with the same
fields the table shows plus `job_id` and `step_id`.

## Bands

An opportunity score falls into one of three bands:

| Score | Band | Meaning |
|---|---|---|
| above 10 | underserved | a real innovation opportunity |
| exactly 10 | appropriate | served; maintain, do not over-invest |
| below 10 | overserved | a candidate for a lower-cost alternative |

`summary` labels the underserved band directly. The classification helper behind
it also recognises `overserved` and `unscored`; those labels appear where a
surface prints a band, not in the plain `summary` table.

## Empty and thin paths

- **Unscored outcome.** An outcome with no importance/satisfaction is
  `unscored`, not zero. `summary` counts it as captured but not underserved.
- **Thin score.** A score sampled from one quote reports `sample_size: null`.
  Do not read it as a market finding — it is one data point.
- **Nothing scored.** `summary` on a job with no outcomes prints the counts and
  an empty opportunities list rather than a placeholder row.

## Not yet delivered

Two surfaces this guide's issue names are not in the tree yet, and are reported
here rather than documented as shipped:

- **Survey import** — there is no survey-import command. Scores are entered by
  hand at `accept` (or `desired-outcomes add`), one outcome at a time.
- **Score history** — the store keeps the current scores; there is no
  history/digest command yet. Read the current landscape with `summary`.

## See also

- [CLI reference](cli.md) — every flag for `score`, `summary`, and `export`.
- [Interviews](interviews.md) — where the scores are entered.
- [The decision artifact](decision.md) — where the landscape becomes a brief.
