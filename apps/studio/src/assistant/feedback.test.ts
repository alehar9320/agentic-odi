import { beforeEach, describe, expect, it } from "vitest";

import { feedbackFor, recordFeedback } from "./feedback";

describe("feedback", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("keeps the verdict a message was given", () => {
    recordFeedback("m-1", "positive");

    expect(feedbackFor("m-1")).toMatchObject({ type: "positive" });
  });

  it("replaces the earlier verdict instead of stacking two", () => {
    recordFeedback("m-1", "positive");
    recordFeedback("m-1", "negative", "missed the point");

    expect(feedbackFor("m-1")).toMatchObject({
      type: "negative",
      comment: "missed the point",
    });
  });

  it("has nothing for a message nobody rated", () => {
    expect(feedbackFor("m-2")).toBeUndefined();
  });

  it("survives other messages being rated", () => {
    recordFeedback("m-1", "negative");
    recordFeedback("m-2", "positive");

    expect(feedbackFor("m-1")?.type).toBe("negative");
    expect(feedbackFor("m-2")?.type).toBe("positive");
  });
});
