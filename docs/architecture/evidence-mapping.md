# Evidence mapping

A connector returns records; ODI needs outcomes. The mapping layer is the narrow
seam between them: it turns a normalized record into an evidence draft, and the
caller decides whether to persist it. This document records that contract and
its deliberate limits.

## What it is

Three shapes, in order:

1. **`IngestRecord`** — `id`, `source_name`, `source_kind`, `item_type`, `name`,
   `content`, `raw` (`packages/connectors/src/agentic_odi_connectors/models.py:36-49`).
   `item_type` is `catalog`, `resource`, or `tool_result`.
2. **`IngestBatch`** — the connector name, its records, and any per-record
   errors.
3. **`EvidenceDraft`** — the mapped record: `source_name`, `source_kind`,
   `item_type`, `name`, `content`, `url`, `raw`, and optional
   `job_id`/`step_id`/`outcome_id` (`mapping.py:17-29`). A draft deliberately has
   no `id`; identity is the store's job.

`drafts_from_batch(batch, job_id=…, step_id=…, outcome_id=…)` walks the batch and
maps each record field-for-field (`mapping.py:53-78`):

- the first six fields are copied as-is;
- `url` is taken only from `raw` keys `url`, `html_url`, `link`, or `uri`;
- `raw` is preserved whole;
- the supplied link ids are stamped onto every draft.

Catalog records are skipped unless `include_catalog=True` (`mapping.py:45-49`):
a connector's own catalog describes the connector, not the customer's job.

Each draft is an `EvidenceDraft` model, so building it validates the required
fields and the item-type enum before anything reaches the service. The package
also exports `validate_evidence_draft()` for a draft that arrives as a plain
dict; the CLI path builds the model directly.

## Why a separate draft

The connector package does not import the ODI service. That keeps a vendor
client from deciding what a customer's evidence means, and it keeps the mapping
unit-testable without a database. The CLI owns the persistence step: when a
target id is supplied, it maps the batch and calls `add_evidence` for each draft;
otherwise the batch only reaches the in-process sink and is lost on exit
(`apps/cli/src/agentic_odi_cli/connectors.py:371-412`).

`add_evidence` then writes an `Evidence` record with the same provenance fields
plus a generated id, validating that any step/outcome id belongs to the named
job (`services.py:507-547`). The result is evidence, not a draft.

## Promotion

`promote_evidence` turns evidence into an ODI artifact (`services.py:589-622`):

- `target="job"` creates a Job whose name is the evidence name and whose
  description is its content.
- `target="outcome"` requires a job id (argument or from the evidence), plus
  **both** importance and satisfaction on the 1–10 scale. The statement is the
  evidence name, or the first non-empty content line. The new outcome inherits
  the evidence's `step_id`, is scored normally, and emits an
  `evidence_promoted` signal.

The evidence itself is not copied into the artifact. There is no back-link from
the Job/Outcome to the evidence record that produced it in the current model;
only the signal names the new outcome.

## Confidence

There is **no confidence field on evidence**, and the mapping does not infer one.
A vendor's confidence survives only inside `raw`. `BusinessValue.confidence`
(0.0–1.0, optional) is a different concept on a different model. Studio memory
observations do carry confidence (default 0.5–0.6, out-of-range values rejected
rather than clamped), but that is the PM memory store, not evidence.

## What the alternatives were

- **Map inside each connector.** Rejected: every vendor would grow its own
  opinion about jobs and outcomes, and the mapping could not be tested once.
- **Let the model summarize records into outcomes at ingest.** Rejected for the
  same reason the statement checker is mechanical: an inferred mapping cannot be
  audited or replayed. Inference belongs to the conversational layer, where a
  person can see and accept it.
- **Dedupe by content hash at ingest.** Not implemented; see below.

## What this does not do

- It does not write the ODI store; the caller persists drafts.
- It does not summarize, score, infer confidence, or classify beyond the three
  item types. Unknown payload keys stay in `raw`.
- It does not discover URLs outside those four raw keys.
- It does not dedupe. Re-running an ingest appends duplicate evidence records
  (and duplicate signals); only REST pagination cursors are deduped at the
  connector level.
- It does not extract a quote from content, and it does not back-link a promoted
  outcome to its evidence. The candidate-outcome review model, where a quote
  becomes a reviewed outcome, is still in progress.
