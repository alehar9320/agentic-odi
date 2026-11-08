# The Method, Stage by Stage

A practitioner's guide to the eight stages of the Universal Job Map, inside this
product. It is not a reference: the flags live in [CLI Reference](cli.md), the
surfaces in [The Living Studio](living-studio.md). What lives here is the
judgement — what each stage is for, what good looks like, the ways it goes wrong, and
the commands that do it.

The stage vocabulary is Ulwick's: **Define, Locate, Prepare, Confirm, Execute,
Monitor, Modify, Conclude** ([`docs/reference/Strategyn_what_is_Outcome_Driven_Innovation.pdf`](reference/Strategyn_what_is_Outcome_Driven_Innovation.pdf)).
Every functional job decomposes into those eight process steps, and the needs are
captured *per step* — which is why the map, not the interview transcript, is the unit
this product stores.

## Before you start

The whole guide follows one job: **Get a month-end reconciliation signed off**, the
work a payments accountant does to prove the ledger matches the bank. Substitute your
own job and the shape still holds.

Two habits make the rest of this work:

* **One store, in order.** Every command below runs against the same SQLite file and
  assumes the commands before it already ran. `$JOB_ID`, `$STEP_ID`, `$OUTCOME_ID` and
  `$EVIDENCE_ID` are the ids the previous command printed — `--json` prints them, and
  `agentic-odi health` confirms the store is reachable before you start writing to it.
  `tests/test_docs_method.py` executes this guide in order against a fixture store and
  fails if a command does not run or references an id nothing created.
* **Outcomes before the map.** `steps add` refuses a job with zero outcomes —
  *"outcomes are what give the steps their meaning"* — because a map with no needs on it
  is a diagram, not research. Capture one outcome first, then build the map, then attach
  the outcome to its step. `--allow-empty-job-map` exists and is audited; reach for it
  only when you are sketching a map on purpose.

The Studio does the same work conversationally: `/jobmap` walks the phases, `/capture`
runs the interview that produces a card, `/landscape` and `/segments` show what the
scores imply ([The Living Studio](living-studio.md)). Neither is a substitute for
knowing what a stage is *for*, which is what the next eight sections are about.

## Define

### What you are trying to learn

What the customer considers the job, in their words, and where they believe it starts
and ends. This is the only stage where the answer can be wrong at the frame level: get
the job wrong and every later need is measured against the wrong thing. The unit of
analysis is the job, not the product you already sell.

### What good looks like

A job statement that survives being handed to a colleague who cannot tell which
product you build. Outcomes at this stage are about scope and intent: the customer's
own metrics for choosing what to work on, phrased as an outcome rather than a task.

Example: `Minimize the time it takes to choose which accounts to reconcile before the
close opens` — a direction, a unit of measure, an object of control, and a context.

### The mistakes

- Solving the job instead of naming it. **Symptom:** the job statement contains the
  name of your product or a feature, and `desired-outcomes evaluate` rejects the
  outcomes that hang off it because they name a solution.
- Choosing a job too wide to be a process. **Symptom:** `agentic-odi summary $JOB_ID`
  reports "0 of 8 phases" no matter how many steps you add, because the steps you can
  think of all land in `Execute`.
- Skipping the already-stored job. **Symptom:** two jobs in `jobs list` with near enough
  the same name, and half the outcomes on each, so nothing clusters.
- Letting the customer's vocabulary be replaced by yours. **Symptom:** every need
  statement uses your internal terms and none of the interview quotes appear in
  `evidence list`.

### Do it here

```bash
agentic-odi jobs add --name "Get a month-end reconciliation signed off" --description "Prove the ledger matches the bank before the close is filed" --json
agentic-odi jobs list --json
agentic-odi desired-outcomes evaluate "Minimize the time it takes to choose which accounts to reconcile before the close opens"
agentic-odi desired-outcomes add --job-id $JOB_ID --statement "Minimize the time it takes to choose which accounts to reconcile before the close opens" --importance 7 --satisfaction 4 --claim-check '{"asked":["How do you decide which accounts get reconciled first?","How long does that decision take?"],"answers":["We go by balance, and it takes an evening."]}' --json
agentic-odi steps add --job-id $JOB_ID --name "Choose which accounts to reconcile" --order 1 --stage define --json
agentic-odi desired-outcomes update $OUTCOME_ID --step-id $STEP_ID
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the number of accounts left out when scoping the month-end close" --importance 6 --satisfaction 5 --json
```

In the Studio, `/jobmap` opens the same map as a lens beside the conversation, and
`/capture` produces the card this command writes
([The Living Studio](living-studio.md)).

**Not in the product yet:** the CLI will not store an outcome before it is scored —
`desired-outcomes add` requires both `--importance` and `--satisfaction`, so a need you
captured in an interview but have not yet rated has to be recorded as an evidence record
(`evidence add`, below) until the numbers exist. The chat and MCP path treats the scores
as optional; [CLI Reference](cli.md) documents the flags either way.

### How you know you are done

The job is in the store and one outcome is attached to a `define` step:

```bash
agentic-odi summary $JOB_ID
agentic-odi desired-outcomes list --job-id $JOB_ID --step-id $STEP_ID
```

Read the `job map` line. `1 of 8 phases` is correct here and is not a warning — the
seven missing phases are the next seven sections.

## Locate

### What you are trying to learn

Where the customer goes to get the inputs they need, and how long that takes them. Most
of the visible pain in a process hides here and in `Prepare`, because nobody measures
hunting for data as work.

### What good looks like

Steps named after what the customer is *trying to get done*, not after the system they
use today. Needs about finding, accessing and receiving — the verbs Ulwick attaches to
this phase are Gather, Access, Receive.

Example: `Minimize the time it takes to obtain the bank statement for the period being
reconciled before matching begins`.

### The mistakes

- Naming the tool instead of the task. **Symptom:** the step is called "Open the bank
  portal", and the outcomes about it argue about portals.
- Treating data availability as data quality. **Symptom:** every outcome here mentions
  accuracy while `Execute` has none, so a matching problem is filed as a locating
  problem.
- Stopping at the first source named. **Symptom:** `evidence list --step-id $STEP_ID`
  returns one record and the map claims six needs.
- Recording the step without any need attached. **Symptom:** `agentic-odi summary
  $JOB_ID` counts the phase as covered while `desired-outcomes list` shows nothing under
  it.

### Do it here

```bash
agentic-odi steps add --job-id $JOB_ID --name "Gather the statements and the ledger" --order 2 --stage locate --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the time it takes to obtain the bank statement for the period being reconciled before matching begins" --importance 8 --satisfaction 3 --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the number of transactions missing a reference when pulling the ledger" --importance 7 --satisfaction 7 --json
agentic-odi evidence add --source-name "Interview: payments accountant" --name "Two days waiting on statements" --content "The statement for account 44 lands on the third day and we reconcile around it." --job-id $JOB_ID --step-id $STEP_ID --json
```

An attached transcript works too: `evidence add --file` reads `.txt`, `.md`, `.vtt` and
`.srt`, or `-` for stdin, and `--url` records where the source lives in your own system
([CLI Reference](cli.md)).

### How you know you are done

Two needs and at least one source on the step, and the phase counted:

```bash
agentic-odi desired-outcomes list --job-id $JOB_ID --step-id $STEP_ID
agentic-odi evidence list --job-id $JOB_ID --step-id $STEP_ID
agentic-odi summary $JOB_ID
```

If `evidence list` prints nothing, the needs on this step are assertions, not research —
that is the gap [ALH-21] reports, and the map will read complete while it stays empty.

## Prepare

### What you are trying to learn

What the customer must set up or organise before the job can be done at all, and which
of that setup is repeated by hand every period. Set Up, Organize, Examine.

### What good looks like

Steps that are recognisably *before* the transaction: importing, arranging, checking
that the workspace is right. Needs here usually carry the biggest speed opportunities
because the work is identical every time.

Example: `Minimize the time it takes to import transactions into the reconciliation tool
before matching starts`.

### The mistakes

- Folding preparation into execution. **Symptom:** `summary $JOB_ID` shows "0 of 8
  phases" for phase 3 while the step you think is Prepare was added with `--order 5`.
- Documenting your solution's setup, not the customer's. **Symptom:** every outcome here
  mentions an import format you invented.
- Accepting a step with one need. **Symptom:** `segments run` reports the outcome as
  unclustered, because a group of one is a hypothesis and not a segment.
- Missing the repeated manual work. **Symptom:** no outcome mentions edits, and the
  interviews are full of them.

### Do it here

```bash
agentic-odi steps add --job-id $JOB_ID --name "Load the period's transactions" --order 3 --stage prepare --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the time it takes to import transactions into the reconciliation tool before matching starts" --importance 9 --satisfaction 4 --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the number of manual edits required after the transactions load" --importance 5 --satisfaction 5 --json
agentic-odi evidence add --source-name "Interview: payments accountant" --name "Edits are re-keyed every month" --content "Twenty rows come in without a cost code and someone types them in again." --job-id $JOB_ID --step-id $STEP_ID --json
```

Where the inputs come from a system rather than an interview, a connector ingests them
as evidence records ([External Connectors](connectors.md)).

### How you know you are done

```bash
agentic-odi desired-outcomes list --job-id $JOB_ID --step-id $STEP_ID
agentic-odi summary $JOB_ID --top 3
```

The coverage line should read `3 of 8 phases`. The `Biggest opportunities` table is a
prioritisation, not a verdict: with a short map it will show you the scores you already
know about.

## Confirm

### What you are trying to learn

How the customer decides they are allowed to proceed, and what they check before the
work becomes expensive to undo. Validate, Prioritize, Decide.

### What good looks like

Needs about the *chance of being wrong*, which is the only honest way to phrase a
validation metric. This is where "minimize the likelihood of ..." belongs.

Example: `Minimize the likelihood of matching an invoice that was already paid during
the prior close`.

### The mistakes

- Writing a control as a need. **Symptom:** the statement names your approval flow, and
  `desired-outcomes evaluate` flags it as naming a solution.
- Confusing confirmation with monitoring. **Symptom:** the same outcome is attached to
  `confirm` and `monitor`, and `segments run` puts both clusters in one bucket.
- Checking only the happy path. **Symptom:** every confirm-phase outcome has
  satisfaction above 6, which usually means nobody asked what happens when the check
  fails.
- Scoring the check instead of the risk. **Symptom:** importance is high because the
  auditor likes the control, not because the customer feels the wait.

### Do it here

```bash
agentic-odi steps add --job-id $JOB_ID --name "Validate the opening balance" --order 4 --stage confirm --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the time it takes to confirm the opening balance while starting the close" --importance 8 --satisfaction 6 --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the likelihood of matching an invoice that was already paid during the prior close" --importance 7 --satisfaction 2 --json
agentic-odi evidence add --source-name "Interview: controller" --name "The double payment is found late" --content "We catch it in audit, weeks after the close, and reverse it then." --job-id $JOB_ID --step-id $STEP_ID --json
```

Score one outcome on this step at or below 10 (`--importance 8 --satisfaction 6` is a
score of 10, appropriately served). You will need a served outcome on the job before
`strategy propose` has evidence to differentiate from, and it is also true research: some
of this job is fine already.

### How you know you are done

```bash
agentic-odi summary $JOB_ID --top 5
agentic-odi evidence list --job-id $JOB_ID --step-id $STEP_ID
```

`4 of 8 phases`, and the opportunity table should now mix underserved needs with at
least one that is not — if every row is above 10, you have recorded complaints rather
than metrics.

## Execute

### What you are trying to learn

The transaction itself: what the customer does to make the job happen, and what makes it
take longer than it should. Perform, Transact, Administer.

### What good looks like

The step the customer would name if you asked them what the job *is*. Outcomes here
usually carry the story you are trying to change, so they need the most evidence behind
them and the clearest claim check on their scores.

Example: `Minimize the time it takes to match a payment to an invoice while closing the
month` — importance 9, satisfaction 3, score 15, underserved.

### The mistakes

- Writing the outcome around your product's happy path. **Symptom:** the statement
  satisfies the format check but no interview quote in `evidence list` uses its words.
- Scoring without asking. **Symptom:** the outcome's `claim_check` comes back with a
  recorded skip and `"verified": false` — which is what happens when you pass numbers
  without `--claim-check`.
- Attaching needs to the wrong step because the map is guesswork. **Symptom:** `steps
  list --job-id $JOB_ID` shows two steps with the same order number.
- Treating one underserved outcome as the answer. **Symptom:** `strategy propose`
  refuses, reporting the segments as unclustered rather than enough evidence to bet on.

### Do it here

```bash
agentic-odi steps add --job-id $JOB_ID --name "Match each payment to an invoice" --order 5 --stage execute --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the time it takes to match a payment to an invoice while closing the month" --importance 9 --satisfaction 3 --claim-check '{"asked":["How long does matching take you?","What happens when it does not match?"],"answers":["Forty minutes, sometimes three hours.","We re-run it the next morning."]}' --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the number of attempts it takes to clear an unmatched payment before signing off the account" --importance 8 --satisfaction 2 --json
agentic-odi evidence add --source-name "Interview: payments accountant" --name "Matching runs past midnight" --content "We re-run the match three times and it still takes until 1am." --job-id $JOB_ID --step-id $STEP_ID --outcome-id $OUTCOME_ID --json
agentic-odi score 9 3
```

`score` is the arithmetic on its own — `importance + max(importance - satisfaction, 0)` —
and it is the fastest way to check a number before you commit to it in an interview.

### How you know you are done

```bash
agentic-odi desired-outcomes list --job-id $JOB_ID --step-id $STEP_ID --json
agentic-odi summary $JOB_ID --top 5
```

`5 of 8 phases`, and in the JSON, `claim_check.verified` is `true` for the outcome you
scored from the interview. An unverified score is not a lie, but it has to say so — that
is the difference between a metric and an assumption.

## Monitor

### What you are trying to learn

How the customer knows the job is going wrong while it is still possible to act: the
signal, and the lag between the signal and the awareness. Verify, Track, Check.

### What good looks like

Needs about *visibility during* the work, distinct from the checks taken before it. If a
statement could be filed under `Confirm` without changing its words, the difference is
timing and it should be explicit.

Example: `Minimize the time it takes to notice a growing variance while reconciling the
ledger`.

### The mistakes

- Describing a feature as a need. **Symptom:** `desired-outcomes evaluate` rejects the
  statement for naming a solution — alerting, dashboards and reports are all in that
  guard on purpose.
- Measuring the alert instead of the awareness. **Symptom:** satisfaction is high
  because a notification exists, while the interview says nobody sees it until the close
  is late.
- Leaving the phase with no needs. **Symptom:** `agentic-odi summary $JOB_ID` reports
  "missing 6" after you are sure you added the step, because the step was given
  `--order 5` as a second step at that order.
- Ignoring what the customer does not look at. **Symptom:** `evidence list` has nothing
  for this step, so the phase's needs are your invention.

### Do it here

```bash
agentic-odi steps add --job-id $JOB_ID --name "Watch the variance while matching" --order 6 --stage monitor --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the time it takes to notice a growing variance while reconciling the ledger" --importance 8 --satisfaction 5 --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the number of surprises found after the variance is already large" --importance 6 --satisfaction 6 --json
agentic-odi evidence add --source-name "Interview: payments accountant" --name "The variance is found on day three" --content "I only see it when I total the column, and I total it once." --job-id $JOB_ID --step-id $STEP_ID --json
```

**Not in the product yet:** nothing records a signal's *source* as a live system here.
`evidence add` stores what a person said or a connector ingested; a metric that arrives
from a running system today comes in through a connector
([External Connectors](connectors.md)) rather than as a monitor-phase measurement.

### How you know you are done

```bash
agentic-odi evidence list --job-id $JOB_ID --step-id $STEP_ID
agentic-odi summary $JOB_ID --top 5
```

`6 of 8 phases`. If the coverage line still lists 6 as missing, read `steps list
--job-id $JOB_ID` and check the order number — coverage counts `--order`, and a step at a
duplicated order does not open a new phase.

## Modify

### What you are trying to learn

What the customer does when the job drifts: the correction, and the cost of making it.
Update, Adjust, Maintain.

### What good looks like

Needs about recovering, not about preventing. This is the phase most product teams
collapse into `Execute`, and the loss is visible in the scores: an outcome about fixing
is scored as though it were the work itself.

Example: `Minimize the time it takes to correct a misposted payment when the variance is
found`.

### The mistakes

- Treating correction as an exception rather than a step. **Symptom:** no outcome
  mentions rework, and the interviews mention it in every session.
- Writing a solution metric. **Symptom:** `Maximize the number of mismatches resolved
  automatically` passes the format check but names your automation, so no customer can
  have said it.
- Scoring the fix by its rarity. **Symptom:** importance is low because it happens twice
  a year, while each occurrence costs a day.
- Forgetting the evidence chain. **Symptom:** `promote_evidence` cannot turn a note into
  an outcome because the note never carried a score.

### Do it here

```bash
agentic-odi steps add --job-id $JOB_ID --name "Correct a misposted payment" --order 7 --stage modify --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the time it takes to correct a misposted payment when the variance is found" --importance 7 --satisfaction 3 --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Maximize the number of mismatches settled without a journal entry when the variance is found" --importance 6 --satisfaction 4 --json
agentic-odi evidence add --source-name "Interview: payments accountant" --name "A correction takes half a day" --content "I reverse it, re-key it, and then prove it to the controller again." --job-id $JOB_ID --step-id $STEP_ID --json
agentic-odi evidence promote $EVIDENCE_ID --to outcome --job-id $JOB_ID --statement "Minimize the time it takes to prove a corrected payment to the controller when audit asks" --importance 6 --satisfaction 3 --json
```

`evidence promote` turns a record into a need. Promoting **to an outcome** requires both
scores — the store will not accept a promoted outcome without them, which is the point:
a promoted claim still has to be a metric.

### How you know you are done

```bash
agentic-odi desired-outcomes list --job-id $JOB_ID --step-id $STEP_ID
agentic-odi summary $JOB_ID --top 5
```

`7 of 8 phases`, and the promoted outcome appears in the list. If it does not, the
promotion created a job instead of an outcome — `--to` decides which.

## Conclude

### What you are trying to learn

How the customer finishes, files, and hands over — and what they still cannot let go of
after the job is done. Store, Finish, Close.

### What good looks like

Needs about the end state: the sign-off, the archive, the audit answer. This phase is
where "done" stops being your definition and becomes theirs.

Example: `Minimize the number of days the close stays open after reconciliation is
finished`.

### The mistakes

- Ending the research at the transaction. **Symptom:** `Execute` holds most of the needs
  and `Conclude` holds one, so the map says the job ends when the work ends.
- Recording the process, not the outcome. **Symptom:** the statement names a filing step
  with no measurable unit and `desired-outcomes evaluate` reports the missing unit of
  measure.
- Signing off on an incomplete map. **Symptom:** `summary $JOB_ID` reads "8 of 8 phases"
  while `desired-outcomes list` shows needs on only four steps.
- Closing without recording what was not covered. **Symptom:** the opportunity landscape
  is presented as the market, and no one can say which phases had three interviews rather
  than none.

### Do it here

```bash
agentic-odi steps add --job-id $JOB_ID --name "Sign the account off and file the evidence" --order 8 --stage conclude --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the time it takes to sign off a reconciled account after the last match is made" --importance 9 --satisfaction 6 --json
agentic-odi desired-outcomes add --job-id $JOB_ID --step-id $STEP_ID --statement "Minimize the number of days the close stays open after reconciliation is finished" --importance 5 --satisfaction 4 --json
agentic-odi evidence add --source-name "Interview: controller" --name "The file is reopened twice" --content "Audit asks for the proof, and we go find it again." --job-id $JOB_ID --step-id $STEP_ID --json
agentic-odi studies open --job $JOB_ID --name "Month-end reconciliation, first pass" --wave 1 --method-notes "Six interviews with accountants and two controllers"
```

The study is a container, not a measurement: it names a wave so a later one is
comparable. `desired-outcomes export --job-id $JOB_ID --format csv` produces the
worksheet you score from the interviews.

### How you know you are done

```bash
agentic-odi summary $JOB_ID --top 5
agentic-odi steps list --job-id $JOB_ID
```

`8 of 8 phases` is the coverage check — the whole map, not the interesting parts. It
still says nothing about depth: Ulwick's research puts most jobs at 8–12 process steps
with 6–12 needs each, roughly 50–150 needs for a job. This product stores eight ordered
phases, so a step beyond the eighth is folded into the phase it belongs to instead of
inventing an order, and sixteen needs is the smallest map that will cluster.

## After the map: what the numbers say

Segmentation and strategy are not job-map phases; they are what the completed map makes
possible. Run them once, in this order, against the store you just filled:

```bash
agentic-odi segments run --job $JOB_ID --json
agentic-odi segments list --job $JOB_ID
agentic-odi strategy propose --job $JOB_ID
agentic-odi strategy show
agentic-odi data-export --job-id $JOB_ID --output odi-export.json
```

A segment is a group of people plus a functional job, and the needs are the evidence for
it, so clustering happens on the job map and never on a demographic. The threshold is
deliberate: **two scored needs on one step**, because a group of one is a hypothesis.
An outcome that joins no cluster is reported as unclustered rather than inflated into a
segment, and `strategy propose` answers with the counts it used — segments in scope,
underserved, overserved, unclustered — when no path has evidence.

That refusal is a feature of this stage. A bet built on nothing is the fabrication the
stage exists to avoid, so `propose` names what is missing instead of recommending
something. When it does recommend, the paths it rejected come back with the reason, and
`strategy show` reads the recorded path later.

Interpreting what the research does not say is the same discipline applied backwards:
a phase with no needs, a segment with one outcome, or a score with no claim check is
reported as the gap it is. Issues ALH-21 and ALH-94 own those surfaces; nothing here sets a
universal bar for "enough research", because a bar that low would be a lie and a bar that
high would be a slogan.

## Where to go next

* [CLI Reference](cli.md) — every flag, backend and environment variable.
* [The Living Studio](living-studio.md) — the same method as a conversation, with
  the `/jobmap`, `/capture`, `/landscape` and `/segments` lenses.
* [External Connectors](connectors.md) — bringing research and system records in as
  evidence.
* [`agentic-odi guidelines`](cli.md) — the stage-by-stage tool guide the assistant
  works from, which is the short form of this document.
