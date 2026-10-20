import { describe, expect, it } from "vitest";

import {
  QUESTION_COUNT,
  REVIEW_INDEX,
  draftFromBrief,
  draftHasContent,
  emptyDraft,
  fieldFromText,
  firstUnanswered,
  isSavePhrase,
  parseSetupIntent,
  questionContent,
  reflectionFor,
  reviewContent,
} from "./setup";

describe("setup conversation model", () => {
  it("asks four questions, each skippable by design", () => {
    expect(QUESTION_COUNT).toBe(4);
  });

  it("resumes at the first unanswered question", () => {
    const draft = { ...emptyDraft(), product_name: "Ambient", target_user: "Engineers" };
    expect(firstUnanswered(draft)).toBe(2);
  });

  it("moves to the review when every question has an answer", () => {
    expect(
      firstUnanswered({
        product_name: "Ambient",
        target_user: "Engineers",
        job_statement: "Ship",
        core_problem: "Drift",
      }),
    ).toBe(REVIEW_INDEX);
  });

  it("reflects an answer before asking the next question", () => {
    const lead = reflectionFor("product_name", "Ambient");
    const content = questionContent(2, emptyDraft(), lead);
    expect(content).toContain("Ambient");
    expect(content).toContain("What job are they trying to get done?");
  });

  it("shows what it will hold, including gaps", () => {
    const content = reviewContent({
      ...emptyDraft(),
      product_name: "Ambient",
      job_statement: "Ship a service",
    });
    expect(content).toContain("**Product** — Ambient");
    expect(content).toContain("**Customer** — —");
    expect(content).toContain("**Job** — Ship a service");
  });

  it("keeps the review honest when nothing was answered", () => {
    expect(reviewContent(emptyDraft())).toContain("completely fine");
    expect(draftHasContent(emptyDraft())).toBe(false);
  });

  it("reads explore, skip, and navigation replies as intents", () => {
    expect(parseSetupIntent("skip")).toEqual({ kind: "skip" });
    expect(parseSetupIntent("I'm not sure")).toEqual({ kind: "skip" });
    expect(parseSetupIntent("not now")).toEqual({ kind: "explore" });
    expect(parseSetupIntent("show me the landscape")).toEqual({
      kind: "panel",
      panel: "landscape",
    });
    expect(parseSetupIntent("open settings")).toEqual({ kind: "panel", panel: "settings" });
    expect(parseSetupIntent("Ambient")).toBeNull();
  });

  it("recognises a save reply and a field change", () => {
    expect(isSavePhrase("looks right")).toBe(true);
    expect(isSavePhrase("that's good")).toBe(true);
    expect(isSavePhrase("change the job")).toBe(false);
    expect(fieldFromText("change the job")).toBe("job_statement");
    expect(fieldFromText("the customer is wrong")).toBe("target_user");
    expect(fieldFromText("the friction changed")).toBe("core_problem");
    expect(fieldFromText("different product")).toBe("product_name");
  });

  it("hydrates from an existing brief for editing", () => {
    const draft = draftFromBrief({
      product_name: "Ambient",
      target_user: "Engineers",
      job_statement: "Ship",
      core_problem: "Drift",
    });
    expect(firstUnanswered(draft)).toBe(REVIEW_INDEX);
    expect(questionContent(0, draft)).toContain("You said: “Ambient”");
  });
});
