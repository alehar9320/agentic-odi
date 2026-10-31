import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OutcomeCard } from "./OutcomeCard";

vi.mock("../../api/studioApi", () => ({
  fetchOutcomeHistory: vi.fn().mockResolvedValue([]),
  fetchOutcomeInterval: vi.fn().mockResolvedValue({ outcome_id: "", band: null }),
}));

const saveThesis = vi.fn();
const pushToast = vi.fn();

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({
    ask: vi.fn(),
    deleteOutcome: vi.fn(),
    pushToast,
    saveThesis,
    updateOutcome: vi.fn(),
    // The card lists the records captured against its outcome; give it an
    // empty canvas so the assertions here stay about the thesis action.
    canvasState: { kind: "ready", data: { jobs: [], steps: [], outcomes: [], source: "seed" } },
    settings: { mcp_url: "http://localhost:8000/mcp" },
  }),
}));

const outcome = {
  id: "O-1",
  job_id: "JOB-1",
  statement: "Minimize the time to propagate secrets when a release ships.",
  importance: 9,
  satisfaction: 3,
  opportunity_score: 15,
};

describe("OutcomeCard thesis action", () => {
  it("opens the form and saves the outcome with its rationale", () => {
    render(<OutcomeCard outcome={outcome} />);

    fireEvent.click(screen.getByRole("button", { name: "Save as thesis" }));
    fireEvent.change(screen.getByLabelText(/Why this bet/i), {
      target: { value: "Secret drift costs senior engineers hours." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save thesis" }));

    expect(saveThesis).toHaveBeenCalledWith({
      outcome_id: "O-1",
      job_id: "JOB-1",
      statement: outcome.statement,
      importance: 9,
      satisfaction: 3,
      opportunity_score: 15,
      rationale: "Secret drift costs senior engineers hours.",
    });
    expect(pushToast).toHaveBeenCalledWith("success", "Opportunity thesis saved");
  });
});
