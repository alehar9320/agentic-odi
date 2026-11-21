import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchExistingSolution, fetchOutcomeAlternatives } from "../../api/studioApi";
import { OutcomeCard } from "./OutcomeCard";

vi.mock("../../api/studioApi", () => ({
  fetchOutcomeHistory: vi.fn().mockResolvedValue([]),
  fetchOutcomeInterval: vi.fn().mockResolvedValue({ outcome_id: "", band: null }),
  fetchOutcomeAlternatives: vi.fn(),
  fetchExistingSolution: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({
    ask: vi.fn(),
    canvasState: { data: { evidence: [] } },
    deleteOutcome: vi.fn(),
    pushToast: vi.fn(),
    updateOutcome: vi.fn(),
    settings: { mcp_url: "http://localhost:8000/mcp" },
  }),
}));

const outcome = {
  id: "O-101",
  statement: "Minimize the time to sync secrets when a deployment starts.",
  importance: 9,
  satisfaction: 2,
  opportunity_score: 16,
};

const alternatives = vi.mocked(fetchOutcomeAlternatives);
const solution = vi.mocked(fetchExistingSolution);

function pair(name: string, kind: string, adequacy: number, usage_n: number | null = null) {
  return {
    alternative: { id: `A-${name}`, job_id: "JOB-1", name, kind },
    link: { outcome_id: "O-101", alternative_id: `A-${name}`, adequacy, usage_n, note: null },
  };
}

describe("OutcomeCard alternatives row", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows a recorded alternative with its adequacy", async () => {
    alternatives.mockResolvedValue([pair("Spreadsheet", "manual", 6.0, 12)] as never);
    solution.mockResolvedValue("yes");

    render(<OutcomeCard outcome={outcome} detail />);

    await waitFor(() =>
      expect(screen.getByTestId("outcome-alternatives")).toHaveTextContent("Spreadsheet"),
    );
    expect(screen.getByTestId("outcome-alternatives")).toHaveTextContent("adequacy 6");
    expect(screen.getByTestId("outcome-alternatives")).toHaveTextContent("n=12");
    expect(screen.getByTestId("outcome-alternatives")).toHaveTextContent(
      "Existing solution: yes",
    );
  });

  it("says not yet inventoried rather than no solution when nothing is recorded", async () => {
    alternatives.mockResolvedValue([]);
    solution.mockResolvedValue("no_link_at_all");

    render(<OutcomeCard outcome={outcome} detail />);

    await waitFor(() =>
      expect(screen.getByTestId("outcome-alternatives")).toHaveTextContent(
        "not yet inventoried",
      ),
    );
    expect(screen.getByTestId("outcome-alternatives")).not.toHaveTextContent("no solution");
  });

  it("distinguishes a recorded nothing row from an un-inventoried outcome", async () => {
    alternatives.mockResolvedValue([pair("Nothing today", "nothing", 1.0)] as never);
    solution.mockResolvedValue("no_linked_nothing");

    render(<OutcomeCard outcome={outcome} detail />);

    await waitFor(() =>
      expect(screen.getByTestId("outcome-alternatives")).toHaveTextContent(
        "the customer uses nothing today",
      ),
    );
    expect(screen.getByTestId("outcome-alternatives")).not.toHaveTextContent(
      "not yet inventoried",
    );
  });

  it("stays quiet when the inventory cannot be read", async () => {
    alternatives.mockRejectedValue(new Error("boom"));
    solution.mockRejectedValue(new Error("boom"));

    render(<OutcomeCard outcome={outcome} detail />);

    await waitFor(() => expect(alternatives).toHaveBeenCalled());
    expect(screen.queryByTestId("outcome-alternatives")).not.toBeInTheDocument();
  });

  it("shows several observations without picking a winner", async () => {
    alternatives.mockResolvedValue([
      pair("Spreadsheet", "manual", 6.0),
      pair("Agency", "service", 4.0),
    ] as never);
    solution.mockResolvedValue("yes");

    render(<OutcomeCard outcome={outcome} detail />);

    await waitFor(() =>
      expect(screen.getByTestId("outcome-alternatives")).toHaveTextContent("Spreadsheet"),
    );
    expect(screen.getByTestId("outcome-alternatives")).toHaveTextContent("Agency");
  });
});
