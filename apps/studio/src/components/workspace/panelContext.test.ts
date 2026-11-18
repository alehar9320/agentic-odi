import { describe, expect, it } from "vitest";

import { stepContextLine } from "./panelContext";
import { JOB_STAGES } from "../../domain/jobStages";

function canvas(steps: Array<{ id?: string; order?: number; name?: string }>) {
  return { jobs: [], steps, outcomes: [], source: "seed" } as never;
}

describe("stepContextLine", () => {
  it("names the step's place and its real name", () => {
    const line = stepContextLine(
      { panel: "jobmap", subject: { kind: "step", id: "S-2" } },
      canvas([
        { id: "S-1", order: 1, name: "Frame the question" },
        { id: "S-2", order: 2, name: "Locate" },
        { id: "S-3", order: 3, name: "Weigh" },
        { id: "S-4", order: 4, name: "Commit" },
      ]),
    );

    expect(line).toBe("Step 2 of 4 • Locate");
  });

  it("falls back to the generated stage name when the step has none", () => {
    const line = stepContextLine(
      { panel: "jobmap", subject: { kind: "step", id: "S-1" } },
      canvas([{ id: "S-1", order: 1 }]),
    );

    expect(line).toBe(`Step 1 of 1 • ${JOB_STAGES[0].name}`);
  });

  it("omits the line when nothing real backs it", () => {
    expect(stepContextLine(null, canvas([]))).toBeNull();
    expect(
      stepContextLine({ panel: "landscape", subject: { kind: "outcome", id: "O-1" } }, canvas([])),
    ).toBeNull();
    expect(
      stepContextLine({ panel: "jobmap", subject: { kind: "step", id: "missing" } }, canvas([])),
    ).toBeNull();
  });
});
