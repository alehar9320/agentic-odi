import type { CanvasData, Job, Outcome, Step } from "../../types";
import { notFound, validation } from "../errors";
import { newId, nowIso } from "../id";
import type { LocalStore, StoredJob, StoredOutcome, StoredStep } from "../store/types";

export function computeOpportunityScore(importance: number, satisfaction: number): number {
  return importance + Math.max(importance - satisfaction, 0);
}

function stripJob(job: StoredJob): Job {
  return { id: job.id, name: job.name, description: job.description };
}

function stripStep(step: StoredStep): Step {
  return {
    id: step.id,
    job_id: step.job_id,
    name: step.name,
    order: step.order,
  };
}

function stripOutcome(outcome: StoredOutcome): Outcome {
  return {
    id: outcome.id,
    job_id: outcome.job_id,
    statement: outcome.statement,
    importance: outcome.importance,
    satisfaction: outcome.satisfaction,
    opportunity_score: outcome.opportunity_score,
  };
}

function validateName(value: string, label: string): string {
  const cleaned = value.trim();
  if (!cleaned) {
    throw validation(`${label} cannot be empty.`);
  }
  return cleaned;
}

function validateScore(value: number | null | undefined, label: string): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (!Number.isFinite(value) || value < 1 || value > 10) {
    throw validation(`${label} must be between 1 and 10.`);
  }
  return value;
}

function validateOrder(value: number): number {
  if (!Number.isInteger(value) || value < 0) {
    throw validation("Step order must be a whole number of zero or more.");
  }
  return value;
}

export class LocalDataService {
  constructor(private readonly store: LocalStore) {}

  async fetchCanvas(): Promise<CanvasData> {
    const [jobs, steps, outcomes] = await Promise.all([
      this.store.listJobs(),
      this.store.listSteps(),
      this.store.listOutcomes(),
    ]);
    return {
      jobs: jobs.map(stripJob),
      steps: steps.map(stripStep),
      outcomes: outcomes.map(stripOutcome),
      source: "local",
    };
  }

  async createJob(input: { name: string; description?: string }): Promise<Job> {
    const now = nowIso();
    const job: StoredJob = {
      id: newId(),
      name: validateName(input.name, "Job name"),
      description: (input.description ?? "").trim(),
      seq: await this.store.nextSeq(),
      created_at: now,
      updated_at: now,
    };
    await this.store.putJob(job);
    return stripJob(job);
  }

  async updateJob(
    jobId: string,
    input: { name?: string; description?: string },
  ): Promise<Job> {
    const existing = await this.store.getJob(jobId);
    if (!existing) {
      throw notFound("Job", jobId);
    }
    const next: StoredJob = {
      ...existing,
      name: input.name === undefined ? existing.name : validateName(input.name, "Job name"),
      description:
        input.description === undefined ? existing.description : input.description.trim(),
      updated_at: nowIso(),
    };
    await this.store.putJob(next);
    return stripJob(next);
  }

  async deleteJob(jobId: string): Promise<{ deleted: string }> {
    if (!(await this.store.getJob(jobId))) {
      throw notFound("Job", jobId);
    }
    const steps = await this.store.listSteps(jobId);
    for (const step of steps) {
      await this.deleteStepCascade(step.id);
    }
    const outcomes = await this.store.listOutcomes(jobId);
    for (const outcome of outcomes) {
      await this.store.deleteOutcome(outcome.id);
    }
    await this.store.deleteJob(jobId);
    return { deleted: jobId };
  }

  async addStep(input: { job_id: string; name: string; order: number }): Promise<Step> {
    if (!(await this.store.getJob(input.job_id))) {
      throw notFound("Job", input.job_id);
    }
    const now = nowIso();
    const step: StoredStep = {
      id: newId(),
      job_id: input.job_id,
      name: validateName(input.name, "Step name"),
      order: validateOrder(input.order),
      seq: await this.store.nextSeq(),
      created_at: now,
      updated_at: now,
    };
    await this.store.putStep(step);
    return stripStep(step);
  }

  async updateStep(
    stepId: string,
    input: { name?: string; order?: number },
  ): Promise<Step> {
    const existing = await this.store.getStep(stepId);
    if (!existing) {
      throw notFound("Step", stepId);
    }
    const next: StoredStep = {
      ...existing,
      name: input.name === undefined ? existing.name : validateName(input.name, "Step name"),
      order: input.order === undefined ? existing.order : validateOrder(input.order),
      updated_at: nowIso(),
    };
    await this.store.putStep(next);
    return stripStep(next);
  }

  async deleteStep(stepId: string): Promise<{ deleted: string }> {
    if (!(await this.store.getStep(stepId))) {
      throw notFound("Step", stepId);
    }
    await this.deleteStepCascade(stepId);
    return { deleted: stepId };
  }

  private async deleteStepCascade(stepId: string): Promise<void> {
    const outcomes = await this.store.listOutcomes();
    for (const outcome of outcomes) {
      if (outcome.step_id === stepId) {
        await this.store.deleteOutcome(outcome.id);
      }
    }
    await this.store.deleteStep(stepId);
  }

  async addOutcome(input: {
    job_id: string;
    statement: string;
    importance: number | null;
    satisfaction: number | null;
    step_id?: string | null;
  }): Promise<Outcome> {
    if (!(await this.store.getJob(input.job_id))) {
      throw notFound("Job", input.job_id);
    }
    if (input.step_id && !(await this.store.getStep(input.step_id))) {
      throw notFound("Step", input.step_id);
    }
    const importance = validateScore(input.importance, "Importance");
    const satisfaction = validateScore(input.satisfaction, "Satisfaction");
    const now = nowIso();
    const outcome: StoredOutcome = {
      id: newId(),
      job_id: input.job_id,
      step_id: input.step_id ?? null,
      statement: validateName(input.statement, "Outcome statement"),
      importance,
      satisfaction,
      opportunity_score:
        importance !== null && satisfaction !== null
          ? computeOpportunityScore(importance, satisfaction)
          : null,
      seq: await this.store.nextSeq(),
      created_at: now,
      updated_at: now,
    };
    await this.store.putOutcome(outcome);
    return stripOutcome(outcome);
  }

  async updateOutcome(
    outcomeId: string,
    input: {
      statement?: string;
      importance?: number | null;
      satisfaction?: number | null;
    },
  ): Promise<Outcome> {
    const existing = await this.store.getOutcome(outcomeId);
    if (!existing) {
      throw notFound("Outcome", outcomeId);
    }
    const importance =
      input.importance === undefined
        ? existing.importance
        : validateScore(input.importance, "Importance");
    const satisfaction =
      input.satisfaction === undefined
        ? existing.satisfaction
        : validateScore(input.satisfaction, "Satisfaction");
    const next: StoredOutcome = {
      ...existing,
      statement:
        input.statement === undefined
          ? existing.statement
          : validateName(input.statement, "Outcome statement"),
      importance,
      satisfaction,
      opportunity_score:
        importance !== null && satisfaction !== null
          ? computeOpportunityScore(importance, satisfaction)
          : null,
      updated_at: nowIso(),
    };
    await this.store.putOutcome(next);
    return stripOutcome(next);
  }

  async deleteOutcome(outcomeId: string): Promise<{ deleted: string }> {
    if (!(await this.store.getOutcome(outcomeId))) {
      throw notFound("Outcome", outcomeId);
    }
    await this.store.deleteOutcome(outcomeId);
    return { deleted: outcomeId };
  }

  async computeOpportunity(importance: number, satisfaction: number): Promise<number> {
    return computeOpportunityScore(
      validateScore(importance, "Importance") ?? importance,
      validateScore(satisfaction, "Satisfaction") ?? satisfaction,
    );
  }
}
