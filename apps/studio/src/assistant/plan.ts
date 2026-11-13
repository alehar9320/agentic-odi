import type { CanvasState } from "../types";
import { JOB_STAGES, type JobStage } from "../domain/jobStages";

export interface PlanEntry {
  stage: JobStage;
  status: "empty" | "partial" | "complete";
  records: number;
}

function stageIndexFor(order: number, stepCount: number): number {
  const stages = JOB_STAGES.length;
  return Math.min(
    Math.max(Math.floor(((order - 1) / Math.max(stepCount, stages)) * stages), 0),
    stages - 1,
  );
}

function emptyPlan(): PlanEntry[] {
  return JOB_STAGES.map((stage) => ({ stage, status: "empty", records: 0 }));
}

/**
 * Where the agent is in the eight ODI stages, derived only from records that
 * exist — never guessed. A stage with zero records is empty, never "in
 * progress"; "complete" is never claimed because a record count alone cannot
 * prove a stage is finished (that would be fabrication).
 */
export function derivePlan(canvasState: CanvasState): PlanEntry[] {
  const canvas = canvasState.data;
  if (!canvas) {
    return emptyPlan();
  }
  const hasRecords =
    canvas.jobs.length > 0 || canvas.steps.length > 0 || canvas.outcomes.length > 0;
  if (!hasRecords) {
    return emptyPlan();
  }

  const counts: Record<string, number> = {};
  // Defining a job is stage one (Define): every job is progress there.
  counts[JOB_STAGES[0].id] = (counts[JOB_STAGES[0].id] ?? 0) + canvas.jobs.length;
  // Steps spread across the phases by their order, the same mapping the Job Map uses.
  const steps = canvas.steps;
  const stepCount = Math.max(steps.length, JOB_STAGES.length);
  for (const step of steps) {
    if (step.order != null) {
      const stage = JOB_STAGES[stageIndexFor(step.order, stepCount)];
      counts[stage.id] = (counts[stage.id] ?? 0) + 1;
    }
  }

  return JOB_STAGES.map((stage) => {
    const records = counts[stage.id] ?? 0;
    return {
      stage,
      status: records === 0 ? "empty" : "partial",
      records,
    };
  });
}
