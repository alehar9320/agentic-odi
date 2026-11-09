import type { CanvasData, Job, Outcome, Step } from "../types";
import { computeOpportunityScore } from "./data/localDataService";
import type { OutboxRecord } from "./store/types";

/**
 * Records a queued write that the sidecar has not acknowledged yet. `sending`
 * counts because a record is in flight, not landed: the canvas must keep
 * showing it until it is `acknowledged`.
 */
const ACTIVE_STATES: readonly OutboxRecord["state"][] = ["pending", "sending"];

function idOf(record: OutboxRecord): string | null {
  return record.local_id ?? record.server_id;
}

function idsFor(
  records: OutboxRecord[],
  entity: OutboxRecord["entity"],
  kind: OutboxRecord["kind"],
): Set<string> {
  const ids = new Set<string>();
  for (const record of records) {
    if (record.entity !== entity || record.kind !== kind) {
      continue;
    }
    const id = idOf(record);
    if (id) {
      ids.add(id);
    }
  }
  return ids;
}

function pendingJob(id: string, payload: unknown): Job {
  const body = (payload ?? {}) as { name?: string; description?: string };
  return { id, name: body.name ?? "", description: body.description ?? "", pending: true };
}

function pendingStep(id: string, payload: unknown): Step {
  const body = (payload ?? {}) as { job_id?: string; name?: string; order?: number };
  return {
    id,
    job_id: body.job_id,
    name: body.name ?? "",
    order: body.order ?? 0,
    pending: true,
  };
}

function pendingOutcome(id: string, payload: unknown): Outcome {
  const body = (payload ?? {}) as {
    job_id?: string;
    statement?: string;
    importance?: number | null;
    satisfaction?: number | null;
  };
  const importance = body.importance ?? null;
  const satisfaction = body.satisfaction ?? null;
  return {
    id,
    job_id: body.job_id,
    statement: body.statement ?? "",
    importance,
    satisfaction,
    opportunity_score:
      importance !== null && satisfaction !== null
        ? computeOpportunityScore(importance, satisfaction)
        : null,
    pending: true,
  };
}

/**
 * Overlay the writes that are still queued on this device onto a canvas read.
 *
 * A read answers with what the sidecar (or the local store) holds, which does
 * not yet include an unacknowledged write. Merging the outbox here is what
 * keeps an optimistic edit on the board across a refresh and a reload: a
 * pending create is added when the canvas omits it, a pending edit marks the
 * row, and a pending delete hides it. Nothing is claimed about the sidecar —
 * every overlaid record is marked `pending`.
 */
export function applyPendingWrites(
  canvas: CanvasData,
  records: OutboxRecord[],
): CanvasData {
  const active = records.filter((record) => ACTIVE_STATES.includes(record.state));
  if (active.length === 0) {
    return canvas;
  }

  const touchedJobs = idsFor(active, "job", "create");
  const touchedSteps = idsFor(active, "step", "create");
  const touchedOutcomes = idsFor(active, "outcome", "create");
  const updatedJobs = idsFor(active, "job", "update");
  const updatedSteps = idsFor(active, "step", "update");
  const updatedOutcomes = idsFor(active, "outcome", "update");
  const deletedJobs = idsFor(active, "job", "delete");
  const deletedSteps = idsFor(active, "step", "delete");
  const deletedOutcomes = idsFor(active, "outcome", "delete");

  const jobs = canvas.jobs
    .filter((job) => !deletedJobs.has(job.id))
    .map((job) =>
      updatedJobs.has(job.id) || touchedJobs.has(job.id) ? { ...job, pending: true } : job,
    );
  const steps = canvas.steps
    .filter((step) => !(step.id && deletedSteps.has(step.id)))
    .map((step) =>
      step.id && (updatedSteps.has(step.id) || touchedSteps.has(step.id))
        ? { ...step, pending: true }
        : step,
    );
  const outcomes = canvas.outcomes
    .filter((outcome) => !(outcome.id && deletedOutcomes.has(outcome.id)))
    .map((outcome) =>
      outcome.id && (updatedOutcomes.has(outcome.id) || touchedOutcomes.has(outcome.id))
        ? { ...outcome, pending: true }
        : outcome,
    );

  for (const record of active) {
    if (record.kind !== "create" || !record.local_id) {
      continue;
    }
    if (record.entity === "job" && !jobs.some((job) => job.id === record.local_id)) {
      jobs.push(pendingJob(record.local_id, record.payload));
    } else if (
      record.entity === "step" &&
      !steps.some((step) => step.id === record.local_id)
    ) {
      steps.push(pendingStep(record.local_id, record.payload));
    } else if (
      record.entity === "outcome" &&
      !outcomes.some((outcome) => outcome.id === record.local_id)
    ) {
      outcomes.push(pendingOutcome(record.local_id, record.payload));
    }
  }

  return { ...canvas, jobs, steps, outcomes };
}
