import { describe, expect, it } from "vitest";

import type { CanvasData } from "../types";
import { MAX_MENTIONS, mentionFormatter, toMentionItems } from "./mentions";

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return {
    jobs: [],
    steps: [],
    outcomes: [],
    source: "mcp",
    ...overrides,
  };
}

const rich = canvas({
  jobs: [
    { id: "J-1", name: "Reconcile a payment" },
    { id: "J-2", name: "Onboard a teammate" },
  ],
  steps: [{ id: "S-1", job_id: "J-1", name: "Find the failure", order: 1 }],
  outcomes: [
    {
      id: "O-1",
      job_id: "J-1",
      statement: "Minimize the time to reconcile",
      opportunity_score: 12.3,
    },
    { id: "O-2", job_id: "J-2", statement: "Minimize the time to get help" },
  ],
  evidence: [
    { id: "E-1", name: "Grain call", source_name: "Grain", content: "We wait hours" },
    { id: "E-2", source_name: "Support", content: "A quote with no name" },
  ],
});

describe("toMentionItems", () => {
  it("returns nothing for a canvas that is not there", () => {
    expect(toMentionItems(null)).toEqual([]);
    expect(toMentionItems(undefined)).toEqual([]);
  });

  it("names jobs, steps, outcomes, and evidence", () => {
    const kinds = toMentionItems(rich).map((item) => item.kind);
    expect(new Set(kinds)).toEqual(new Set(["job", "step", "outcome", "evidence"]));
  });

  it("uses the record's own id, never a made-up one", () => {
    const ids = toMentionItems(rich).map((item) => item.id);
    expect(ids).toContain("J-1");
    expect(ids).toContain("O-1");
    expect(ids).toContain("E-1");
  });

  it("leaves out a record with no id rather than inventing one", () => {
    const noIds = canvas({
      jobs: [{ name: "No id here" }],
      outcomes: [{ statement: "Also no id" }],
      evidence: [{ id: "", name: "Empty id" }],
    });
    expect(toMentionItems(noIds)).toEqual([]);
  });

  it("falls back to a plain label when a record is unnamed", () => {
    const unnamed = canvas({ jobs: [{ id: "J-9" }], outcomes: [{ id: "O-9" }] });
    const labels = toMentionItems(unnamed).map((item) => item.label);
    expect(labels).toContain("Untitled job");
    expect(labels).toContain("Untitled outcome");
  });

  it("carries the kind and the owning job in the hint", () => {
    const outcome = toMentionItems(rich).find((item) => item.id === "O-1");
    expect(outcome?.hint).toContain("Outcome");
    expect(outcome?.hint).toContain("Reconcile a payment");
    expect(outcome?.hint).toContain("12.3");
  });

  it("orders by recency when nothing is typed", () => {
    const ids = toMentionItems(rich).map((item) => item.id);
    expect(ids.indexOf("E-2")).toBeLessThan(ids.indexOf("J-1"));
  });

  it("ranks an exact id match first", () => {
    const ids = toMentionItems(rich, "O-2").map((item) => item.id);
    expect(ids[0]).toBe("O-2");
  });

  it("ranks a label starts-with above a later hit", () => {
    const ids = toMentionItems(rich, "minimize").map((item) => item.id);
    // Both outcomes start with "Minimize"; the evidence does not.
    expect(ids.slice(0, 2).sort()).toEqual(["O-1", "O-2"]);
  });

  it("caps the list", () => {
    const many = canvas({
      jobs: Array.from({ length: MAX_MENTIONS + 20 }, (_, index) => ({
        id: `J-${index}`,
        name: `Job ${index}`,
      })),
    });
    expect(toMentionItems(many)).toHaveLength(MAX_MENTIONS);
  });
});

describe("mentionFormatter", () => {
  it("serializes a chosen mention as the literal @id", () => {
    expect(
      mentionFormatter.serialize({ id: "O-1", type: "outcome", label: "Minimize the time" }),
    ).toBe("@O-1");
  });

  it("never turns typed text into a chip", () => {
    expect(mentionFormatter.parse("@O-1 please look")).toEqual([
      { kind: "text", text: "@O-1 please look" },
    ]);
    expect(mentionFormatter.parse("")).toEqual([]);
  });
});
