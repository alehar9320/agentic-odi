import { describe, expect, it } from "vitest";

import { computeOpportunityScore } from "./localDataService";
import { MemoryLocalStore } from "../store/memoryStore";
import { LocalDataService } from "./localDataService";

function makeStore() {
  return new MemoryLocalStore();
}

describe("computeOpportunityScore", () => {
  it("scores importance plus the gap to satisfaction", () => {
    expect(computeOpportunityScore(8, 3)).toBe(13);
    expect(computeOpportunityScore(3, 8)).toBe(3);
    expect(computeOpportunityScore(5, 5)).toBe(5);
  });
});

describe("LocalDataService canvas", () => {
  it("returns an empty canvas with source local", async () => {
    const store = makeStore();
    const service = new LocalDataService(store);
    const canvas = await service.fetchCanvas();
    expect(canvas.source).toBe("local");
    expect(canvas.jobs).toEqual([]);
    expect(canvas.steps).toEqual([]);
    expect(canvas.outcomes).toEqual([]);
    expect(canvas.provenance?.kind).toBe("empty");
    expect(canvas.provenance?.reason).toBe("local_store_empty");
  });

  it("creates jobs and steps in insertion order", async () => {
    const store = makeStore();
    const service = new LocalDataService(store);
    const jobA = await service.createJob({ name: "Job A" });
    const jobB = await service.createJob({ name: "Job B" });
    const step1 = await service.addStep({
      job_id: jobA.id,
      name: "Step 1",
      order: 1,
    });
    const step0 = await service.addStep({
      job_id: jobA.id,
      name: "Step 0",
      order: 0,
    });

    const canvas = await service.fetchCanvas();
    expect(canvas.jobs.map((j) => j.id)).toEqual([jobA.id, jobB.id]);
    expect(canvas.steps.map((s) => s.id)).toEqual([step0.id, step1.id]);
  });
});

describe("job CRUD", () => {
  it("validates job names", async () => {
    const store = makeStore();
    const service = new LocalDataService(store);
    await expect(service.createJob({ name: "   " })).rejects.toThrow();
  });

  it("updates and deletes a job", async () => {
    const store = makeStore();
    const service = new LocalDataService(store);
    const job = await service.createJob({ name: "Original" });
    const updated = await service.updateJob(job.id, { name: "Renamed" });
    expect(updated.name).toBe("Renamed");
    await expect(service.deleteJob(job.id)).resolves.toEqual({ deleted: job.id });
    const canvas = await service.fetchCanvas();
    expect(canvas.jobs.find((j) => j.id === job.id)).toBeUndefined();
  });
});

describe("outcome scoring and cascades", () => {
  it("computes opportunity score on create and update", async () => {
    const store = makeStore();
    const service = new LocalDataService(store);
    const job = await service.createJob({ name: "Job" });
    const outcome = await service.addOutcome({
      job_id: job.id,
      statement: "Reduce setup time",
      importance: 8,
      satisfaction: 3,
    });
    expect(outcome.opportunity_score).toBe(13);

    const updated = await service.updateOutcome(outcome.id as string, {
      satisfaction: 9,
    });
    expect(updated.opportunity_score).toBe(8);
  });

  it("cascades outcomes when a job is deleted", async () => {
    const store = makeStore();
    const service = new LocalDataService(store);
    const job = await service.createJob({ name: "Job" });
    await service.addOutcome({
      job_id: job.id,
      statement: "Outcome",
      importance: 5,
      satisfaction: 5,
    });
    await service.deleteJob(job.id);
    const canvas = await service.fetchCanvas();
    expect(canvas.outcomes).toEqual([]);
  });
});

describe("row provenance", () => {
  it("marks a row the studio created as the customer's own", async () => {
    const service = new LocalDataService(makeStore());
    const job = await service.createJob({ name: "Job A" });
    const step = await service.addStep({ job_id: job.id, name: "Step 1", order: 1 });
    const outcome = await service.addOutcome({
      job_id: job.id,
      step_id: step.id,
      statement: "Minimize the time it takes to sign up when onboarding",
      importance: 8,
      satisfaction: 3,
    });

    expect(job.origin).toBe("user");
    expect(step.origin).toBe("user");
    expect(outcome.origin).toBe("user");
  });

  it("carries origin through the canvas instead of dropping it", async () => {
    const store = makeStore();
    const service = new LocalDataService(store);
    const job = await service.createJob({ name: "Job A" });
    await service.addStep({ job_id: job.id, name: "Step 1", order: 1 });
    const stored = await store.getJob(job.id);
    await store.putJob({ ...stored!, origin: "demo" });

    const canvas = await service.fetchCanvas();

    expect(canvas.jobs[0].origin).toBe("demo");
    expect(canvas.steps[0].origin).toBe("user");
  });
});
