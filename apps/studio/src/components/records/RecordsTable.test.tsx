import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CanvasData } from "../../types";
import { buildRecords } from "../../lib/records";
import { RecordsTable } from "./RecordsTable";

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return { jobs: [], steps: [], outcomes: [], source: "mcp", ...overrides };
}

describe("RecordsTable", () => {
  it("renders one section per kind that has rows", () => {
    const rows = buildRecords(
      canvas({
        jobs: [{ id: "J-1", name: "Activation" }],
        outcomes: [{ id: "O-1", job_id: "J-1", statement: "Get to first value" }],
      }),
    );
    render(<RecordsTable rows={rows} />);
    expect(screen.getByRole("heading", { name: /jobs/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /desired outcomes/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /steps/i })).toBeNull();
    expect(screen.queryByRole("heading", { name: /evidence/i })).toBeNull();
  });

  it("says unscored rather than showing a number it did not get", () => {
    const rows = buildRecords(canvas({ outcomes: [{ id: "O-1", importance: 8, satisfaction: 4 }] }));
    const { container } = render(<RecordsTable rows={rows} />);
    expect(screen.getByText("unscored")).toBeInTheDocument();
    expect(container.textContent).not.toContain("12");
  });

  it("caps a section at 200 rows and says how many it hid", () => {
    const outcomes = Array.from({ length: 250 }, (_, index) => ({
      id: `O-${index}`,
      statement: `Outcome ${index}`,
    }));
    const { container } = render(<RecordsTable rows={buildRecords(canvas({ outcomes }))} />);
    expect(container.querySelectorAll("code.records__id")).toHaveLength(200);
    expect(screen.getByText(/showing first 200 of 250/i)).toBeInTheDocument();
  });

  it("explains an empty store instead of rendering an empty table", () => {
    render(<RecordsTable rows={[]} />);
    expect(screen.getByText(/no records yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});
