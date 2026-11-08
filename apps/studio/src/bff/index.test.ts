import { afterEach, describe, expect, it, vi } from "vitest";

import { StudioBff } from "./index";
import { MemoryLocalStore } from "./store/memoryStore";

afterEach(() => {
  vi.unstubAllGlobals();
});

function makeBff() {
  const store = new MemoryLocalStore();
  return new StudioBff(store);
}

describe("StudioBff workspace export/import", () => {
  it("exports an empty workspace as JSON with version 1", async () => {
    const bff = makeBff();
    const json = await bff.exportWorkspace();
    const snapshot = JSON.parse(json);
    expect(snapshot.version).toBe(1);
    expect(snapshot.exported_at).toBeDefined();
    expect(snapshot.jobs).toEqual([]);
    expect(snapshot.steps).toEqual([]);
    expect(snapshot.outcomes).toEqual([]);
    expect(snapshot.observations).toEqual([]);
    expect(snapshot.conversations).toEqual([]);
    expect(snapshot.turns).toEqual([]);
  });

  it("round-trips canvas data through export and import", async () => {
    const bff = makeBff();
    const job = await bff.data.createJob({ name: "Job A" });
    await bff.data.createJob({ name: "Job B" });
    await bff.data.addStep({ job_id: job.id, name: "Step", order: 0 });

    const json = await bff.exportWorkspace();
    const snapshot = JSON.parse(json);
    expect(snapshot.jobs).toHaveLength(2);
    expect(snapshot.steps).toHaveLength(1);

    const fresh = makeBff();
    await fresh.importWorkspace(json);
    const canvas = await fresh.data.fetchCanvas();
    expect(canvas.jobs.map((j) => j.name).sort()).toEqual(["Job A", "Job B"]);
    expect(canvas.steps).toHaveLength(1);
  });

  it("rejects invalid JSON on import", async () => {
    const bff = makeBff();
    await expect(bff.importWorkspace("not json")).rejects.toThrow();
  });

  it("rejects unsupported workspace version on import", async () => {
    const bff = makeBff();
    await expect(
      bff.importWorkspace(JSON.stringify({ version: 2 })),
    ).rejects.toThrow();
  });

  it("importFromSidecar returns false when local already has data", async () => {
    const bff = makeBff();
    await bff.data.createJob({ name: "Existing" });
    const imported = await bff.importFromSidecar("http://mcp/mcp");
    expect(imported).toBe(false);
  });

  it("importFromSidecar imports canvas and memory when local is empty", async () => {
    const bff = makeBff();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/canvas")) {
          return new Response(
            JSON.stringify({
              jobs: [{ id: "j-1", name: "Sidecar Job" }],
              steps: [
                { id: "s-1", job_id: "j-1", name: "Sidecar Step", order: 0 },
              ],
              outcomes: [
                {
                  id: "o-1",
                  job_id: "j-1",
                  statement: "Sidecar outcome",
                  importance: 8,
                  satisfaction: 3,
                },
              ],
              source: "mcp",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (url.includes("/api/memory/observations")) {
          return new Response(
            JSON.stringify({
              observations: [
                {
                  id: "obs-1",
                  kind: "evidence",
                  text: "Sidecar observation",
                  data: {},
                  status: "confirmed",
                  confidence: 0.9,
                  source_turn: null,
                  created_at: "2026-01-01T00:00:00Z",
                  updated_at: "2026-01-01T00:00:00Z",
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(JSON.stringify({}), { status: 404 });
      }),
    );

    const imported = await bff.importFromSidecar("http://mcp/mcp");
    expect(imported).toBe(true);

    const canvas = await bff.data.fetchCanvas();
    expect(canvas.jobs.map((j) => j.name)).toEqual(["Sidecar Job"]);
    expect(canvas.steps.map((s) => s.name)).toEqual(["Sidecar Step"]);
    expect(canvas.outcomes.map((o) => o.statement)).toEqual([
      "Sidecar outcome",
    ]);
    expect(canvas.outcomes[0].opportunity_score).toBe(13);

    const memory = await bff.memory.listObservations();
    expect(memory).toHaveLength(1);
    expect(memory[0].text).toBe("Sidecar observation");

    vi.unstubAllGlobals();
  });
});

describe("StudioBff capture queue", () => {
  it("queues a capture and counts it until it syncs", async () => {
    const bff = makeBff();
    const job = await bff.data.createJob({ name: "Ship a service" });

    const queued = await bff.queueCapture({
      job_id: job.id,
      statement: "Minimize the time it takes to ship",
      importance: 8,
      satisfaction: 3,
    });
    expect(queued.pending).toBe(true);
    expect(await bff.countQueuedCaptures()).toBe(1);
    expect((await bff.listQueuedCaptures()).map((o) => o.statement)).toEqual([
      "Minimize the time it takes to ship",
    ]);
  });

  it("replays each capture at most once across a losing second call", async () => {
    const bff = makeBff();
    const job = await bff.data.createJob({ name: "Ship a service" });
    await bff.queueCapture({
      job_id: job.id,
      statement: "Minimize the time it takes to ship",
      importance: 8,
      satisfaction: 3,
    });

    const keys: string[] = [];
    const send = (record: { id: string }) => {
      keys.push(record.id);
    };
    await bff.replayCaptures(send);
    await bff.replayCaptures(send);

    expect(keys).toHaveLength(1);
    expect(await bff.countQueuedCaptures()).toBe(0);
  });

  it("keeps a refused capture and surfaces it instead of dropping it", async () => {
    const bff = makeBff();
    const job = await bff.data.createJob({ name: "Ship a service" });
    const queued = await bff.queueCapture({
      job_id: job.id,
      statement: "Minimize the time it takes to ship",
      importance: 8,
      satisfaction: 3,
    });

    await bff.failQueuedCapture(queued.id, "The sidecar refused this capture.");

    expect(await bff.countQueuedCaptures()).toBe(0);
    expect(await bff.listFailedCaptures()).toHaveLength(1);
    // The record is kept, not deleted: nothing is silently dropped.
    expect(await bff.store.getOutbox(queued.id)).toMatchObject({
      state: "failed",
      last_error: "The sidecar refused this capture.",
    });
  });

  it("drops a queued capture the person no longer wants", async () => {
    const bff = makeBff();
    const job = await bff.data.createJob({ name: "Ship a service" });
    const queued = await bff.queueCapture({
      job_id: job.id,
      statement: "Minimize the time it takes to ship",
      importance: 8,
      satisfaction: 3,
    });

    await bff.discardQueuedCapture(queued.id);
    expect(await bff.countQueuedCaptures()).toBe(0);
    await expect(bff.discardQueuedCapture(queued.id)).rejects.toThrow();
  });
});
