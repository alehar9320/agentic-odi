import { afterEach, describe, expect, it, vi } from "vitest";

import { StudioBff, parseWorkspaceSnapshot } from "./index";
import { WORKSPACE_SNAPSHOT_VERSION } from "./store/types";
import { MemoryLocalStore } from "./store/memoryStore";

afterEach(() => {
  vi.unstubAllGlobals();
});

function makeBff() {
  const store = new MemoryLocalStore();
  return new StudioBff(store);
}

describe("StudioBff workspace export/import", () => {
  it("exports an empty workspace as JSON at the current version", async () => {
    const bff = makeBff();
    const json = await bff.exportWorkspace();
    const snapshot = JSON.parse(json);
    expect(snapshot.version).toBe(WORKSPACE_SNAPSHOT_VERSION);
    expect(snapshot.exported_at).toBeDefined();
    expect(snapshot.jobs).toEqual([]);
    expect(snapshot.steps).toEqual([]);
    expect(snapshot.outcomes).toEqual([]);
    expect(snapshot.observations).toEqual([]);
    expect(snapshot.evidence).toEqual([]);
    expect(snapshot.conversations).toEqual([]);
    expect(snapshot.turns).toEqual([]);
    expect(snapshot.pending_writes_excluded).toBe(false);
  });

  it("round-trips every record at the current version", async () => {
    const bff = makeBff();
    const job = await bff.data.createJob({ name: "Job A" });
    await bff.data.createJob({ name: "Job B" });
    await bff.data.addStep({ job_id: job.id, name: "Step", order: 0 });
    await bff.data.addOutcome({
      job_id: job.id,
      statement: "Minimize the time it takes to decide",
      importance: 8,
      satisfaction: 3,
    });
    await bff.memory.addObservation({
      kind: "evidence",
      text: "A recorded observation",
      confidence: 0.9,
      confirmed: true,
    });

    const json = await bff.exportWorkspace();
    const snapshot = JSON.parse(json);
    expect(snapshot.version).toBe(WORKSPACE_SNAPSHOT_VERSION);
    expect(snapshot.jobs).toHaveLength(2);
    expect(snapshot.steps).toHaveLength(1);
    expect(snapshot.outcomes).toHaveLength(1);
    expect(snapshot.observations).toHaveLength(1);

    const fresh = makeBff();
    await fresh.importWorkspace(json);
    const canvas = await fresh.data.fetchCanvas();
    expect(canvas.jobs.map((j) => j.name).sort()).toEqual(["Job A", "Job B"]);
    expect(canvas.steps).toHaveLength(1);
    expect(canvas.outcomes).toHaveLength(1);
    const memory = await fresh.memory.listObservations();
    expect(memory).toHaveLength(1);
    expect(memory[0].text).toBe("A recorded observation");

    // Re-exporting a restored workspace keeps every record.
    const reexported = JSON.parse(await fresh.exportWorkspace());
    expect(reexported.jobs).toEqual(snapshot.jobs);
    expect(reexported.outcomes).toEqual(snapshot.outcomes);
    expect(reexported.turns).toEqual(snapshot.turns);
  });

  it("migrates a version 1 file, keeping every record and adding empty new stores", async () => {
    const v1 = {
      version: 1,
      jobs: [
        {
          id: "j-1",
          name: "Legacy job",
          description: "",
          seq: 1,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      steps: [],
      outcomes: [],
      observations: [],
      conversations: [],
      turns: [],
      exported_at: "2026-01-02T00:00:00Z",
    };

    const bff = makeBff();
    await bff.importWorkspace(JSON.stringify(v1));

    const canvas = await bff.data.fetchCanvas();
    expect(canvas.jobs.map((j) => j.name)).toEqual(["Legacy job"]);

    // A v1 file has no evidence, so the migrated workspace has an empty store.
    const summary = await bff.workspaceSummary();
    expect(summary.counts.evidence).toBe(0);
    expect(summary.counts.jobs).toBe(1);
  });

  it("reports a version mismatch instead of swallowing it", async () => {
    const bff = makeBff();
    await expect(
      bff.importWorkspace(JSON.stringify({ version: 99, jobs: [] })),
    ).rejects.toThrow(/version 99/);
  });

  it("rejects a payload with no version at all", async () => {
    const bff = makeBff();
    await expect(bff.importWorkspace(JSON.stringify({ jobs: [] }))).rejects.toThrow(
      /version none/,
    );
  });

  it("rejects invalid JSON on import", async () => {
    const bff = makeBff();
    await expect(bff.importWorkspace("not json")).rejects.toThrow();
  });

  it("marks pending writes as excluded from the file", async () => {
    const bff = makeBff();
    await bff.store.enqueueOutbox({
      id: "out-1",
      kind: "create",
      entity: "job",
      local_id: "j-1",
      server_id: null,
      payload: {},
      depends_on: [],
      state: "pending",
      attempts: 0,
      last_error: null,
      created_at: "2026-01-01T00:00:00Z",
      acknowledged_at: null,
    });

    const snapshot = JSON.parse(await bff.exportWorkspace());
    expect(snapshot.pending_writes_excluded).toBe(true);
  });

  it("summarizes an empty workspace", async () => {
    const bff = makeBff();
    const summary = await bff.workspaceSummary();
    expect(summary.empty).toBe(true);
    expect(summary.records).toBe(0);
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

describe("parseWorkspaceSnapshot", () => {
  it("reads a current-version file with its evidence", () => {
    const parsed = parseWorkspaceSnapshot(
      JSON.stringify({
        version: WORKSPACE_SNAPSHOT_VERSION,
        jobs: [],
        steps: [],
        outcomes: [],
        observations: [],
        evidence: [{ id: "e-1", source_name: "Gong", name: "Call" }],
        conversations: [],
        turns: [],
      }),
    );
    expect(parsed.version).toBe(WORKSPACE_SNAPSHOT_VERSION);
    expect(parsed.evidence).toHaveLength(1);
  });

  it("treats a missing list as empty rather than throwing", () => {
    const parsed = parseWorkspaceSnapshot(
      JSON.stringify({ version: WORKSPACE_SNAPSHOT_VERSION }),
    );
    expect(parsed.jobs).toEqual([]);
    expect(parsed.evidence).toEqual([]);
  });

  it("refuses a payload that is not an object", () => {
    expect(() => parseWorkspaceSnapshot("[]")).toThrow(/not a workspace snapshot/);
  });
});
