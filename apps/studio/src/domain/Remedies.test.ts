// Remedies interface: the effort vocabulary and the labelled examples (#741).
import { describe, expect, it } from "vitest";

import { getRemedies, isRemedyEffort } from "./Remedies";

describe("getRemedies", () => {
  it("returns two illustrative remedies for any finding", () => {
    const remedies = getRemedies({ kind: "outcome", id: "O-1" });

    expect(remedies).toHaveLength(2);
    for (const remedy of remedies) {
      expect(remedy.id).toBeTruthy();
      expect(remedy.title).toBeTruthy();
      expect(remedy.rationale).toBeTruthy();
      expect(isRemedyEffort(remedy.effort)).toBe(true);
      // The whole point of the issue: nothing unbacked may read as real.
      expect(remedy.source).toBe("illustrative");
    }
  });

  it("gives every remedy a distinct id", () => {
    const ids = getRemedies({ kind: "outcome", id: "O-1" }).map((remedy) => remedy.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("hands out copies, so a caller cannot mutate the shared mock", () => {
    const first = getRemedies({ kind: "outcome", id: "O-1" });
    first[0].title = "changed";
    const second = getRemedies({ kind: "outcome", id: "O-1" });
    expect(second[0].title).not.toBe("changed");
  });
});

describe("isRemedyEffort", () => {
  it("accepts the closed vocabulary and refuses anything else", () => {
    expect(isRemedyEffort("small")).toBe(true);
    expect(isRemedyEffort("medium")).toBe(true);
    expect(isRemedyEffort("large")).toBe(true);
    expect(isRemedyEffort("trivial")).toBe(false);
    expect(isRemedyEffort(3)).toBe(false);
    expect(isRemedyEffort(undefined)).toBe(false);
  });
});
