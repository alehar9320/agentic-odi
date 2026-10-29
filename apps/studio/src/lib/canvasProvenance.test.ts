import { describe, expect, it } from "vitest";

import type { CanvasData } from "../types";
import { canvasStatus, isSimulatedCanvas } from "./canvasProvenance";

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return {
    jobs: [],
    steps: [],
    outcomes: [],
    source: "local",
    ...overrides,
  };
}

describe("canvas provenance", () => {
  it("treats seed provenance as simulated", () => {
    const data = canvas({
      source: "seed",
      provenance: {
        kind: "seed",
        reason: "mcp_unreachable",
        generated_at: "2026-10-29T10:00:00+00:00",
        record_counts: { jobs: 1, steps: 8, outcomes: 5, evidence: 0 },
      },
    });

    expect(isSimulatedCanvas(data)).toBe(true);
    expect(canvasStatus(data)).toEqual({
      label: "OFFLINE",
      detail: "sample data — the MCP server could not be reached",
    });
  });

  it("labels a seed canvas that is not an outage as DEMO", () => {
    const data = canvas({
      source: "seed",
      provenance: {
        kind: "seed",
        reason: "demo",
        generated_at: "2026-10-29T10:00:00+00:00",
        record_counts: { jobs: 1, steps: 8, outcomes: 5, evidence: 0 },
      },
    });

    expect(canvasStatus(data)?.label).toBe("DEMO");
  });

  it("falls back to source for a cache written before provenance existed", () => {
    expect(isSimulatedCanvas(canvas({ source: "seed" }))).toBe(true);
    expect(isSimulatedCanvas(canvas({ source: "mcp" }))).toBe(false);
  });

  it("has no label for live, empty, or missing canvases", () => {
    expect(canvasStatus(canvas({ source: "mcp" }))).toBeNull();
    expect(canvasStatus(null)).toBeNull();
  });
});
