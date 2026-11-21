// Session verbatims interface: provenance decides what the quotes claim (#741).
import { describe, expect, it } from "vitest";

import type { CanvasProvenance } from "../types";
import { getSessionEvidence } from "./Verbatims";

const provenance = (evidence: number): CanvasProvenance => ({
  kind: "live",
  reason: "local_store",
  generated_at: "2026-11-15T00:00:00.000Z",
  record_counts: { jobs: 1, steps: 0, outcomes: 2, evidence },
});

describe("getSessionEvidence", () => {
  it("labels the mock quotes as illustrative", () => {
    const evidence = getSessionEvidence({ kind: "outcome", id: "O-1" });

    expect(evidence.basis).toBe("illustrative");
    expect(evidence.quotes.length).toBeGreaterThan(0);
    for (const quote of evidence.quotes) {
      // Mapped straight onto the Evidence fields it will come from.
      expect(quote.content).toBeTruthy();
      expect(quote.source_name).toBeTruthy();
      expect(quote.source_kind).toBeTruthy();
    }
  });

  it("reports the real evidence count when provenance exists", () => {
    const evidence = getSessionEvidence({ kind: "outcome", id: "O-1" }, provenance(142));
    expect(evidence.count).toBe(142);
  });

  it("hides the count rather than inventing one when provenance is absent", () => {
    expect(getSessionEvidence({ kind: "outcome", id: "O-1" }).count).toBeNull();
    expect(getSessionEvidence({ kind: "outcome", id: "O-1" }, null).count).toBeNull();
  });

  it("reports a real zero as zero, not as absent", () => {
    // A provenance that says there are no evidence records is a real answer;
    // it must not be confused with "nothing told us the count".
    expect(getSessionEvidence({ kind: "outcome", id: "O-1" }, provenance(0)).count).toBe(0);
  });

  it("hands out copies, so a caller cannot mutate the shared mock", () => {
    const first = getSessionEvidence({ kind: "outcome", id: "O-1" });
    first.quotes[0].content = "changed";
    const second = getSessionEvidence({ kind: "outcome", id: "O-1" });
    expect(second.quotes[0].content).not.toBe("changed");
  });
});
