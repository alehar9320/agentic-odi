import { describe, expect, it } from "vitest";

import type { CanvasData } from "../types";
import { buildRecords, RECORD_SECTIONS, toCsv, type RecordRow } from "./records";

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

describe("toCsv", () => {
  function shortRow(cells: string[]): RecordRow {
    return {
      kind: "job",
      rowKey: "job:1",
      id: null,
      parentId: null,
      cells,
      record: { id: "J-1" },
    };
  }

  it("returns an empty string for a store with nothing in it", () => {
    expect(toCsv([])).toBe("");
  });

  // The shape the person opening the file in a spreadsheet sees: one header, then each
  // section introduced by the same label the lens prints, in the same order.
  it("writes the header, then each section's label and rows, joined by CRLF", () => {
    const csv = toCsv(
      buildRecords(
        canvas({
          jobs: [{ id: "J-1", name: "Onboarding", description: "First week" }],
          outcomes: [
            { id: "O-1", job_id: "J-1", statement: "Ship faster", opportunity_score: 12.5 },
          ],
        }),
      ),
    );
    expect(csv.split("\r\n")).toEqual([
      "Name,Description,Id",
      "Jobs",
      "Onboarding,First week,J-1",
      "Desired outcomes",
      "Ship faster,—,—,12.5,J-1,O-1",
    ]);
  });

  it("skips a section the lens would not show", () => {
    const csv = toCsv(buildRecords(canvas({ evidence: [{ id: "E-1", name: "Call" }] })));
    expect(csv.split("\r\n")).toEqual(["Name,Description,Id", "Evidence", "—,—,—,Call,—,E-1"]);
    expect(csv).not.toContain("Jobs");
  });

  it("quotes a value that holds a comma", () => {
    const csv = toCsv(buildRecords(canvas({ jobs: [{ id: "J-1", name: "Mid, market" }] })));
    expect(csv).toContain('"Mid, market"');
  });

  it("escapes an embedded quote by doubling it", () => {
    const csv = toCsv(buildRecords(canvas({ jobs: [{ id: "J-1", name: 'He said "no"' }] })));
    expect(csv).toContain('"He said ""no"""');
  });

  it("quotes a value that holds a newline, so the row stays one row", () => {
    const csv = toCsv(buildRecords(canvas({ jobs: [{ id: "J-1", name: "First\nSecond" }] })));
    expect(csv).toContain('"First\nSecond"');
    // The break belongs to the field, not to the record: three lines, not four.
    expect(csv.split("\r\n")).toHaveLength(3);
  });

  it("leaves a plain value unquoted", () => {
    expect(toCsv([shortRow(["Onboarding", "First week", "J-1"])])).toBe(
      "Name,Description,Id\r\nJobs\r\nOnboarding,First week,J-1",
    );
  });

  // The header promises a column count; a record missing a cell must keep the other
  // columns lined up rather than shifting them left.
  it("writes an empty cell, never the word undefined, when a record is short", () => {
    const csv = toCsv([shortRow(["Onboarding"])]);
    expect(csv.split("\r\n")[2]).toBe("Onboarding,,");
    expect(csv).not.toContain("undefined");
  });

  it("exports the word unscored, not a number, for an outcome with no score", () => {
    const csv = toCsv(buildRecords(canvas({ outcomes: [{ id: "O-1", importance: 8 }] })));
    expect(csv.split("\r\n")[2]).toBe("—,8,—,unscored,—,O-1");
  });

  it("ends on the last record, with no trailing break", () => {
    expect(toCsv([shortRow(["Onboarding", "First week", "J-1"])])).not.toMatch(/\r\n$/);
  });
});

