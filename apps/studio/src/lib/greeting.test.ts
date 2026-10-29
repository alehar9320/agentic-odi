import { describe, expect, it } from "vitest";

import {
  greetingCandidates,
  nextGreeting,
  timeOfDayGreeting,
  type GreetingContext,
} from "./greeting";

function context(overrides: Partial<GreetingContext> = {}): GreetingContext {
  return {
    now: new Date("2026-10-20T09:30:00"),
    jobCount: 0,
    outcomeCount: 0,
    underservedCount: 0,
    llmHealthy: true,
    ...overrides,
  };
}

describe("timeOfDayGreeting", () => {
  it("greets the morning between 05:00 and 11:59", () => {
    expect(timeOfDayGreeting(new Date("2026-10-20T05:00:00"))).toBe("Good morning");
    expect(timeOfDayGreeting(new Date("2026-10-20T11:59:00"))).toBe("Good morning");
  });

  it("greets the afternoon between 12:00 and 17:59", () => {
    expect(timeOfDayGreeting(new Date("2026-10-20T12:00:00"))).toBe("Good afternoon");
    expect(timeOfDayGreeting(new Date("2026-10-20T17:59:00"))).toBe("Good afternoon");
  });

  it("greets the evening overnight", () => {
    expect(timeOfDayGreeting(new Date("2026-10-20T18:00:00"))).toBe("Good evening");
    expect(timeOfDayGreeting(new Date("2026-10-20T03:00:00"))).toBe("Good evening");
  });
});

describe("greetingCandidates", () => {
  it("leads with the invitation, not the clock", () => {
    const [first] = greetingCandidates(context());
    expect(first).toEqual({
      id: "capability-win",
      text: "What do you want to win?",
      kind: "capability",
    });
  });

  it("uses the display name in the greeting that follows", () => {
    const greeting = greetingCandidates(context({ displayName: "  Ada  " })).find(
      (candidate) => candidate.id === "greeting",
    );
    expect(greeting?.text).toBe("Good morning, Ada");
  });

  it("offers one greeting and one invitation first", () => {
    const kinds = greetingCandidates(context()).slice(0, 2).map(({ kind }) => kind);
    expect(kinds).toEqual(["capability", "greeting"]);
  });

  it("reflects the opportunity landscape once outcomes exist", () => {
    const insight = greetingCandidates(
      context({ outcomeCount: 4, underservedCount: 1, jobCount: 2 }),
    ).find((candidate) => candidate.id === "insight-outcomes");

    expect(insight?.text).toBe("4 outcomes mapped — 1 underserved.");
  });

  it("stays honest about the canvas when nothing is underserved", () => {
    const insight = greetingCandidates(context({ outcomeCount: 1 })).find(
      (candidate) => candidate.id === "insight-outcomes",
    );

    expect(insight?.text).toBe("1 outcome mapped. Nothing is starving for attention.");
  });

  it("offers a capability line when the canvas is empty", () => {
    const kinds = greetingCandidates(context()).map((candidate) => candidate.kind);
    expect(kinds).toContain("capability");
    expect(kinds).not.toContain("insight");
  });

  it("mentions local mode only when the model is unreachable", () => {
    const offline = greetingCandidates(context({ llmHealthy: false }));
    const online = greetingCandidates(context({ llmHealthy: true }));

    expect(offline.some((candidate) => candidate.kind === "status")).toBe(true);
    expect(online.some((candidate) => candidate.kind === "status")).toBe(false);
  });
});

describe("nextGreeting", () => {
  const candidates = greetingCandidates(context({ displayName: "Ada" }));

  it("advances to the next candidate", () => {
    expect(nextGreeting(candidates, candidates[0].id)?.id).toBe(candidates[1].id);
  });

  it("wraps around to the first headline", () => {
    const last = candidates[candidates.length - 1];
    expect(nextGreeting(candidates, last.id)?.id).toBe(candidates[0].id);
  });

  it("starts at the first headline when nothing is current", () => {
    expect(nextGreeting(candidates, null)?.id).toBe(candidates[0].id);
  });

  it("returns null for an empty rotation", () => {
    expect(nextGreeting([], "greeting")).toBeNull();
  });
});
