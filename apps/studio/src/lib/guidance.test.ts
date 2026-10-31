import { describe, expect, it } from "vitest";

import {
  GUIDANCE_STORAGE_KEY,
  currentGuidance,
  readDismissedGuidance,
  writeDismissedGuidance,
  type GuidanceInput,
  type GuidanceStorage,
} from "./guidance";
import type { StudioBrief } from "../types";

const BRIEF: StudioBrief = {
  product_name: "Ambient",
  target_user: "Platform engineers",
  job_statement: "Get a service from commit to production",
  core_problem: "A missed config key costs hours",
};

function input(overrides: Partial<GuidanceInput> = {}): GuidanceInput {
  return {
    brief: null,
    messageCount: 1,
    outcomeCount: 0,
    evidenceCount: 0,
    dismissed: [],
    ...overrides,
  };
}

function memoryStorage(): GuidanceStorage & { value: string | null } {
  const holder = {
    value: null as string | null,
    getItem: () => holder.value,
    setItem: (_key: string, value: string) => {
      holder.value = value;
    },
  };
  return holder;
}

describe("currentGuidance", () => {
  it("says nothing before the first exchange", () => {
    expect(currentGuidance(input({ messageCount: 0 }))).toBeNull();
  });

  it("asks for context once the studio has replied", () => {
    expect(currentGuidance(input())?.id).toBe("context");
  });

  it("stays quiet when the brief is known", () => {
    expect(currentGuidance(input({ brief: BRIEF }))).toBeNull();
  });

  it("asks for the evidence a score is missing", () => {
    const guidance = currentGuidance(
      input({ brief: BRIEF, outcomeCount: 3, evidenceCount: 0 }),
    );
    expect(guidance?.id).toBe("evidence");
    expect(guidance?.action).toBe("capture");
  });

  it("does not ask for evidence that already exists", () => {
    expect(
      currentGuidance(input({ brief: BRIEF, outcomeCount: 3, evidenceCount: 2 })),
    ).toBeNull();
  });

  it("puts context ahead of evidence", () => {
    expect(
      currentGuidance(input({ outcomeCount: 3, evidenceCount: 0 }))?.id,
    ).toBe("context");
  });

  it("honours a permanent dismissal", () => {
    expect(currentGuidance(input({ dismissed: ["context"] }))).toBeNull();
    expect(
      currentGuidance(input({ brief: BRIEF, outcomeCount: 1, dismissed: ["evidence"] })),
    ).toBeNull();
  });

  it("moves on to the next hint after a dismissal", () => {
    const guidance = currentGuidance(
      input({ brief: BRIEF, outcomeCount: 1, dismissed: ["context"] }),
    );
    expect(guidance?.id).toBe("evidence");
  });
});

describe("guidance dismissal storage", () => {
  it("round-trips known ids", () => {
    const storage = memoryStorage();
    writeDismissedGuidance(["context"], storage);
    expect(storage.value).toBe(JSON.stringify(["context"]));
    expect(readDismissedGuidance(storage)).toEqual(["context"]);
  });

  it("ignores malformed or unknown records", () => {
    const storage = memoryStorage();
    storage.value = "not json";
    expect(readDismissedGuidance(storage)).toEqual([]);

    storage.value = JSON.stringify(["context", "nonsense", 3]);
    expect(readDismissedGuidance(storage)).toEqual(["context"]);
  });

  it("treats missing storage as an empty dismissal list", () => {
    expect(readDismissedGuidance(null)).toEqual([]);
    expect(GUIDANCE_STORAGE_KEY).toBe("studio.guidance");
  });
});
