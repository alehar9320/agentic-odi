import { describe, expect, it } from "vitest";

import type { CanvasData, SignalSubjectKind } from "../types";
import { focusLabel, focusPointer } from "./focus";

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return { jobs: [], steps: [], outcomes: [], source: "local", ...overrides };
}

const SUBJECTS: readonly SignalSubjectKind[] = [
  "job",
  "step",
  "outcome",
  "evidence",
  "connector",
  "agent_work",
  "segment",
  "strategy",
];

describe("focusPointer", () => {
  it("passes every kind the store can read back", () => {
    for (const kind of ["job", "step", "outcome", "evidence"] as const) {
      expect(focusPointer({ kind, id: "X-1" })).toEqual({ kind, id: "X-1" });
    }
  });

  it("drops every kind the store cannot read back", () => {
    const readable = SUBJECTS.filter((kind) => focusPointer({ kind, id: "X-1" }) !== null);
    expect(readable).toEqual(["job", "step", "outcome", "evidence"]);
  });

  it("is nothing at all when the screen has selected nothing", () => {
    expect(focusPointer(null)).toBeNull();
  });
});

describe("focusLabel", () => {
  it("names a focused outcome with the statement the store holds", () => {
    const board = canvas({
      outcomes: [{ id: "O-9", statement: "Reduce the time to reconcile a failed payment" }],
    });

    expect(focusLabel(board, { kind: "outcome", id: "O-9" })).toBe(
      "Reduce the time to reconcile a failed payment",
    );
  });

  it("names a focused job, step, and evidence with their own words", () => {
    const board = canvas({
      jobs: [{ id: "J-1", name: "Reconcile a payment" }],
      steps: [{ id: "S-1", job_id: "J-1", name: "Match the ledger line" }],
      evidence: [{ id: "E-1", job_id: "J-1", name: "Call with the ops lead" }],
    });

    expect(focusLabel(board, { kind: "job", id: "J-1" })).toBe("Reconcile a payment");
    expect(focusLabel(board, { kind: "step", id: "S-1" })).toBe("Match the ledger line");
    expect(focusLabel(board, { kind: "evidence", id: "E-1" })).toBe("Call with the ops lead");
  });

  it("says nothing about a kind the pointer will not carry", () => {
    const board = canvas({ jobs: [{ id: "J-1", name: "Reconcile a payment" }] });

    expect(focusLabel(board, { kind: "strategy", id: "J-1" })).toBeNull();
  });

  it("says nothing about an id this snapshot does not hold", () => {
    const board = canvas({ outcomes: [{ id: "O-9", statement: "An outcome" }] });

    expect(focusLabel(board, { kind: "outcome", id: "no-such-outcome" })).toBeNull();
  });

  it("says nothing before the canvas has loaded", () => {
    expect(focusLabel(null, { kind: "outcome", id: "O-9" })).toBeNull();
  });

  it("says nothing when nothing is selected", () => {
    expect(focusLabel(canvas({ jobs: [{ id: "J-1", name: "A job" }] }), null)).toBeNull();
  });

  it("falls back to the store's own word for a record with no name", () => {
    expect(focusLabel(canvas({ jobs: [{ id: "J-1" }] }), { kind: "job", id: "J-1" })).toBe("—");
  });
});
