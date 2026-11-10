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
