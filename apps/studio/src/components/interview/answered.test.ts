/**
 * The answered record's pure mapping (issue #400).
 *
 * The summary line and the record links are read from what the store
 * confirmed, never from the answers: a submission that wrote nothing must say
 * `0 outcomes`. These tests pin that arithmetic without a renderer.
 */

import { describe, expect, it } from "vitest";

import { answeredSummaryLine, notSavedLine, plural, recordLinks } from "./answered";

const questions = [
  { id: "job", prompt: "The job?" },
  { id: "outcome", prompt: "The outcome?" },
  { id: "importance", prompt: "How important?" },
];

describe("answeredSummaryLine", () => {
  it("counts the answers given and the records the store confirmed", () => {
    const line = answeredSummaryLine({
      questions,
      answers: { job: "A job", outcome: "An outcome", importance: 9 },
      created: { outcomeIds: ["o-1", "o-2"], evidenceCount: 1 },
    });

    expect(line).toBe("Answered · 3 of 3 · 2 outcomes, 1 evidence");
  });

  it("uses the singular for a count of one", () => {
    const line = answeredSummaryLine({
      questions,
      answers: { job: "A job", outcome: "An outcome", importance: 9 },
      created: { outcomeIds: ["o-1"], evidenceCount: 1 },
    });

    expect(line).toBe("Answered · 3 of 3 · 1 outcome, 1 evidence");
  });

  it("reads 0 outcomes when the answers produced no records", () => {
    const line = answeredSummaryLine({
      questions,
      answers: { job: "A job", outcome: "An outcome", importance: 9 },
      created: { outcomeIds: [], evidenceCount: 0 },
    });

    expect(line).toBe("Answered · 3 of 3 · 0 outcomes, 0 evidence");
  });

  it("counts only the questions that were actually answered", () => {
    const line = answeredSummaryLine({
      questions,
      answers: { job: "A job", importance: 5 },
      created: { outcomeIds: [], evidenceCount: 0 },
    });

    expect(line).toContain("Answered · 2 of 3");
  });

  it("treats a blank string as unanswered and a numeric zero as answered", () => {
    const line = answeredSummaryLine({
      questions: [
        { id: "blank", prompt: "blank" },
        { id: "zero", prompt: "zero" },
      ],
      answers: { blank: "   ", zero: 0 },
      created: { outcomeIds: [], evidenceCount: 0 },
    });

    expect(line).toContain("Answered · 1 of 2");
  });
});

describe("recordLinks", () => {
  it("offers one link per created outcome, in creation order", () => {
    expect(recordLinks({ outcomeIds: ["o-1", "o-2"], evidenceCount: 3 })).toEqual([
      { id: "o-1", label: "Outcome 1" },
      { id: "o-2", label: "Outcome 2" },
    ]);
  });

  it("offers nothing when no outcome was created", () => {
    expect(recordLinks({ outcomeIds: [], evidenceCount: 2 })).toEqual([]);
  });
});

describe("notSavedLine", () => {
  it("names the reason a write stopped", () => {
    expect(notSavedLine("the store refused it")).toBe("Not saved — the store refused it");
  });

  it("says the write did not complete when no reason was given", () => {
    expect(notSavedLine("  ")).toBe("Not saved — the write did not complete.");
  });
});

describe("plural", () => {
  it("is singular at one and plural otherwise", () => {
    expect(plural(1, "turn", "turns")).toBe("turn");
    expect(plural(0, "turn", "turns")).toBe("turns");
    expect(plural(2, "turn", "turns")).toBe("turns");
  });
});
