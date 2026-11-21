import { describe, expect, it } from "vitest";
import { derivePlan } from "./plan";
import type { CanvasData, CanvasState } from "../types";

function canvas(overrides: Partial<CanvasData> = {}): CanvasState {
  return {
    kind: "ready",
    data: { jobs: [], steps: [], outcomes: [], source: "local", ...overrides },
  } as unknown as CanvasState;
}

describe("derivePlan", () => {
  it("returns eight empty entries for an empty canvas", () => {
    const plan = derivePlan(canvas());
    expect(plan).toHaveLength(8);
    for (const entry of plan) {
      expect(entry.status).toBe("empty");
      expect(entry.records).toBe(0);
    }
  });

  it("marks one stage partial for a jobs-only canvas", () => {
    const plan = derivePlan(canvas({ jobs: [{ id: "J-1", name: "Deploy" }] }));
    const partial = plan.filter((entry) => entry.status === "partial");
    expect(partial).toHaveLength(1);
    expect(partial[0].stage.id).toBe("define");
    for (const entry of plan) {
      if (entry.status === "empty") {
        expect(entry.records).toBe(0);
      }
    }
  });

  it("maps steps to their stage by order", () => {
    const plan = derivePlan(canvas({ steps: [{ id: "S-1", order: 1 }] }));
    const partial = plan.filter((entry) => entry.status === "partial");
    expect(partial).toHaveLength(1);
    expect(partial[0].stage.id).toBe("define");
  });

  it("never claims complete from record counts alone", () => {
    const plan = derivePlan(
      canvas({ steps: [{ id: "S-1", order: 1 }], jobs: [{ id: "J-1" }] }),
    );
    for (const entry of plan) {
      expect(entry.status).not.toBe("complete");
    }
  });

  it("treats a non-ready canvas as empty", () => {
    const plan = derivePlan({ kind: "error", error: { code: "x", message: "y", retryable: false }, data: null } as unknown as CanvasState);
    expect(plan).toHaveLength(8);
    for (const entry of plan) {
      expect(entry.status).toBe("empty");
    }
  });
});
