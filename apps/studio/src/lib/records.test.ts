import { describe, expect, it } from "vitest";

import type { CanvasData } from "../types";
import { buildRecords, RECORD_SECTIONS } from "./records";

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return { jobs: [], steps: [], outcomes: [], source: "local", ...overrides };
}

describe("buildRecords", () => {
  it("returns nothing for a canvas that has not loaded", () => {
    expect(buildRecords(null)).toEqual([]);
    expect(buildRecords(undefined)).toEqual([]);
  });

  it("lists the four kinds in section order", () => {
    const rows = buildRecords(
      canvas({
        jobs: [{ id: "J-1" }],
        steps: [{ id: "S-1", job_id: "J-1", order: 1 }],
        outcomes: [{ id: "O-1", job_id: "J-1" }],
        evidence: [{ id: "E-1", job_id: "J-1" }],
      }),
    );
    expect(rows.map((row) => row.kind)).toEqual(["job", "step", "outcome", "evidence"]);
    expect(rows).toHaveLength(4);
  });

  it("never invents a score and never prints undefined", () => {
    const [row] = buildRecords(
      canvas({ outcomes: [{ id: "O-1", importance: 8, satisfaction: 4 }] }),
    );
    expect(row.cells[0]).toBe("—");
    expect(row.cells[3]).toBe("unscored");
  });

  it("renders a stored score exactly as the server returned it", () => {
    const [row] = buildRecords(canvas({ outcomes: [{ id: "O-1", opportunity_score: 12.3 }] }));
    expect(row.cells[3]).toBe("12.3");
  });

  it("keeps a record with no id addressable", () => {
    const rows = buildRecords(canvas({ steps: [{ name: "Onboarding" }, { name: "Activation" }] }));
    expect(rows).toHaveLength(2);
    expect(rows[0].id).toBeNull();
    expect(rows[0].cells[3]).toBe("—");
    expect(new Set(rows.map((row) => row.rowKey)).size).toBe(2);
  });

  it("points evidence at the closest parent it has", () => {
    const [row] = buildRecords(
      canvas({ evidence: [{ id: "E-1", job_id: "J-1", outcome_id: "O-1" }] }),
    );
    expect(row.parentId).toBe("O-1");
  });
});

describe("RECORD_SECTIONS", () => {
  it("ends every section with the id column", () => {
    for (const section of RECORD_SECTIONS) {
      expect(section.columns[section.columns.length - 1]).toBe("Id");
    }
  });
});
