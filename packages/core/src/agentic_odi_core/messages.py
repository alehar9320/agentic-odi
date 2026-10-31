from agentic_odi_core.contract import capability_summary

ODI_ASSISTANT_PROMPT = """You are an expert in Outcome-Driven Innovation (ODI). Your purpose is to help users discover, define, and prioritize high-value jobs, desired outcomes, and opportunities."""

ODI_FRAMEWORK_GUIDELINES = """## Outcome-Driven Innovation (ODI) — Stage-by-Stage Tool Guide

Follow this sequence when guiding a user through the ODI process:

### Stage 1: Define Intent (Job-to-be-Done)
- **When**: Always start here if no Job exists.
- **Ask the user**: 'What is the main task or goal your customer is trying to accomplish?'
- **Tools to use**:
  - `add_job(name, description)` — Create the Job once identified.
  - `get_jobs()` — Check if a relevant Job already exists before creating a new one.
  - `get_job(job_id)` — Retrieve details of a specific existing Job.

### Stage 2: Capture Desired Outcomes
- **When**: After a Job is defined. Outcomes come BEFORE steps or solutions.
- **Ask the user**: 'What does success look like? What should happen faster, more reliably, or more consistently?'
- **Outcome statement format**: `[Direction] + [Unit of Measure] + [Object of Control] + [Contextual Clarifier]`, e.g. 'Minimize the time it takes to onboard a new engineer.'
- **Direction**: Must start with 'Minimize' or 'Maximize'.
- **Unit of measure**: A measurable unit (time, cost, number, frequency, rate, percentage, steps, attempts).
- **Object of control**: The thing being acted on (named after 'the').
- **Contextual clarifier**: When it happens (when, while, before, after, during, if, as).
- **Scores**: Both `importance` and `satisfaction` are required (1–10). An outcome without them cannot be compared to anything.
- **Expectation**: Qualitative interviews typically uncover 50–150 desired outcome statements.
- **Tools to use**:
  - `add_outcome(job_id, statement, importance, satisfaction)` — Capture each desired outcome with scores.
  - `get_outcomes(job_id)` — Review all outcomes captured for a Job.
  - `evaluate_outcome(statement, job_id?)` — **Pre-write check**: run this before `add_outcome` to confirm the statement matches the ODI format. It returns coded issues and suggestions for any failure.
  - `update_outcome(outcome_id, ...)` — Correct a statement or scores; the same validation applies.

### Stage 3: Build the Job Map
- **When**: After key outcomes are captured. Never build a map on a job with zero outcomes — outcomes are what give the steps their meaning.
- **Ask the user**: 'What are the key phases or steps the customer takes when doing this job?'
- **Eight Universal Job Map stages** (in order): Define, Locate, Prepare, Confirm, Execute, Monitor, Modify, Conclude.
- **Tools to use**:
  - `add_step(job_id, name, order, stage?)` — Add each chronological step; `stage` must be one of the eight stages above, and `stage_index` is derived from it.
  - `get_job_map(job_id)` — View the complete ordered job map, ordered by stage.

### Stage 4: Calculate Opportunity Scores
- **When**: After outcomes have importance and satisfaction scores.
- **Formula**: Opportunity Score = importance + max(importance - satisfaction, 0)
- **Scores > 10** indicate high innovation opportunity. Guide the user to focus efforts there.
- **Scores ≤ 10** indicate appropriately served or overserved outcomes.
- **Tools to use**: `get_outcomes(job_id)` — Review opportunity_score field on each outcome. `compute_opportunity(importance, satisfaction)` — Calculate a score directly.

### Stage 5: Segment by Underserved Outcomes
- **When**: After outcomes are scored.
- **Never** segment by demographics. A segment is a group of people plus a functional job.
- **Tools**: `get_segments(job_id?)`, `propose_strategy()`.
- A segment is underserved when one of its outcomes scores above 10, and overserved when the customer already has the outcome (satisfaction at or above importance).

### Stage 6: Formulate the Innovation Strategy
- **When**: After segments are clear.
- **Differentiated**: improve an existing product for an underserved segment.
- **Disruptive**: offer a lower-cost solution to an overserved segment.
- **New-Market**: create for a job no one is being served on today.
- **Tools**: `propose_strategy(job_id?)`.
- Always state the strategies you rejected and why.

### General Rule
Never skip stages. Always confirm the user has a Job defined (Stage 1) before capturing Outcomes (Stage 2), always capture Outcomes (Stage 2) before building the Job Map (Stage 3), and always score outcomes (Stage 2) before computing opportunity (Stage 4). If a tool rejects a write, read the message, fix the statement or the numbers, and try once. Do not retry the same call unchanged."""


def get_odi_framework_guidelines() -> str:
    return ODI_FRAMEWORK_GUIDELINES


CAPABILITIES = capability_summary()


def job_not_found(job_id: str) -> str:
    return f"Job not found: {job_id}"


def customer_outcome_not_found(outcome_id: str) -> str:
    return f"Customer outcome not found: {outcome_id}"


def step_not_found(step_id: str | None) -> str:
    return f"Step not found: {step_id}"


def outcome_not_found(outcome_id: str | None) -> str:
    return f"Outcome not found: {outcome_id}"


def evidence_not_found(evidence_id: str | None, hint: str | None = None) -> str:
    message = f"Evidence not found: {evidence_id}"
    if hint:
        message = f"{message}. {hint}"
    return message


def scheduled_work_not_found(work_id: str | None, hint: str | None = None) -> str:
    message = f"Scheduled work not found: {work_id}"
    if hint:
        message = f"{message}. {hint}"
    return message


def interview_not_found(interview_id: str | None) -> str:
    return f"Interview not found: {interview_id}"


def quote_not_found(quote_id: str | None) -> str:
    return f"Quote not found: {quote_id}"


def candidate_not_found(candidate_id: str | None) -> str:
    return f"Outcome candidate not found: {candidate_id}"


def candidate_reason_required(candidate_id: str | None) -> str:
    return (
        f"A rejection reason is required for outcome candidate {candidate_id}; "
        "the reason is kept beside the candidate so the decision is defensible."
    )


def merge_target_must_be_outcome(target_id: str | None) -> str:
    return (
        f"Merge target {target_id} is not an accepted outcome. Accept the candidate first, "
        "then merge other candidates into the outcome it produced."
    )


def merge_source_already_merged(candidate_id: str | None, merged_into: str | None) -> str:
    return (
        f"Outcome candidate {candidate_id} is already merged into {merged_into}; "
        "repeating the merge changes nothing."
    )


def merge_source_cannot_absorb_evidence(candidate_id: str | None, status: str | None) -> str:
    return (
        f"Outcome candidate {candidate_id} is {status}, so its evidence cannot be absorbed. "
        "Only a proposed candidate can be merged into an outcome."
    )
