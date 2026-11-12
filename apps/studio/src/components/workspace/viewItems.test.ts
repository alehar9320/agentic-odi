import { describe, expect, it } from "vitest";

import type { CanvasData } from "../../types";
import { deriveViewItems } from "./viewItems";

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return {
    jobs: [],
    steps: [],
    outcomes: [],
    source: "seed",
    ...overrides,
  };
}

describe("deriveViewItems", () => {
  it("returns nothing for an empty board", () => {
    expect(deriveViewItems(null, [], [])).toEqual([]);
    expect(deriveViewItems(canvas(), [], [])).toEqual([]);
  });

  it("counts outcomes, steps, evidence, and records", () => {
    const items = deriveViewItems(
      canvas({
        jobs: [{ id: "J-1", name: "Job" }],
        steps: [{ id: "S-1", name: "Step", order: 1 }],
        outcomes: [
          { id: "O-1", evidence: "a quote" },
          { id: "O-2" },
        ],
        evidence: [{ id: "E-1" }],
      }),
      [{ id: "m-1" }] as never,
      [{ id: "seg-1" }] as never,
    );

    expect(items.map((item) => [item.id, item.count])).toEqual([
      ["records", 5],
      ["landscape", 2],
      ["jobmap", 1],
      ["segments", 1],
      ["evidence", 1],
      ["memory", 1],
    ]);
  });

  it("agrees with the rail on every label and count", () => {
    const items = deriveViewItems(
      canvas({ outcomes: [{ id: "O-1", evidence: "quote" }] }),
      [],
      [],
    );

    expect(items).toEqual([
      { id: "records", label: "Records", count: 1, noun: "record" },
      { id: "landscape", label: "Landscape", count: 1, noun: "opportunity" },
      { id: "evidence", label: "Evidence", count: 1, noun: "signal" },
    ]);
  });
});
