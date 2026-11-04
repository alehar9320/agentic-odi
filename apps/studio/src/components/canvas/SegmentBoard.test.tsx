import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CanvasData, Segment } from "../../types";
import { SegmentBoard } from "./SegmentBoard";

const CANVAS: CanvasData = {
  jobs: [{ id: "JOB-1", name: "Rotate secrets" }],
  steps: [{ id: "STEP-1", job_id: "JOB-1", name: "Rotate the secret", order: 5 }],
  outcomes: [
    {
      id: "O-1",
      statement: "Minimize the time to rotate a secret",
      importance: 9,
      satisfaction: 2,
      opportunity_score: 16,
    },
    {
      id: "O-2",
      statement: "Minimize the risk of a stale credential",
      importance: 8,
      satisfaction: 4,
      opportunity_score: 12,
    },
    {
      id: "O-3",
      statement: "Minimize the effort of auditing access",
      importance: 7,
      satisfaction: 5,
      opportunity_score: null,
    },
  ],
  source: "seed",
};

function segment(overrides: Partial<Segment> = {}): Segment {
  return {
    id: "SEG-1",
    job_id: "JOB-1",
    name: "Platform engineers, secrets rotation",
    people: "the people working on secrets",
    people_inferred: true,
    job_statement: "Rotate secrets without breaking a deploy",
    outcome_ids: ["O-1", "O-2"],
    verdict: "underserved",
    rationale: "Two outcomes on Rotate the secret; one scores above 10.",
    confidence: 0.8,
    created_at: "2026-10-31T00:00:00Z",
    ...overrides,
  };
}

const harness = vi.hoisted(() => ({
  state: {
    segments: [] as unknown[],
    strategy: null as unknown,
    segmentsError: null as unknown,
    refreshSegments: vi.fn(),
    canvas: null as unknown,
    settings: { mcp_url: "http://localhost:8000/mcp" },
    pushToast: vi.fn(),
    sendMessage: vi.fn(),
    closePanel: vi.fn(),
    focusSubject: vi.fn(),
    openPanel: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

describe("SegmentBoard", () => {
  beforeEach(() => {
    harness.state.segments = [];
    harness.state.strategy = null;
    harness.state.segmentsError = null;
    harness.state.canvas = CANVAS;
    harness.state.refreshSegments.mockClear();
    harness.state.focusSubject.mockClear();
    harness.state.openPanel.mockClear();
    harness.state.sendMessage.mockClear();
    harness.state.closePanel.mockClear();
  });

  it("shows each segment's member outcomes with their stored scores", () => {
    harness.state.segments = [segment()];

    render(<SegmentBoard />);

    const card = screen.getByLabelText("Segment: Platform engineers, secrets rotation");
    const members = within(card).getAllByRole("button", { name: /^Open O-/ });
    expect(members).toHaveLength(2);
    expect(members[0]).toHaveTextContent("O-1");
    expect(members[0]).toHaveTextContent("Minimize the time to rotate a secret");
    expect(members[0]).toHaveTextContent("16.0");
    expect(members[1]).toHaveTextContent("12.0");
  });

  it("states the mean over scored members and the unscored count", () => {
    harness.state.segments = [segment({ outcome_ids: ["O-1", "O-3"] })];

    render(<SegmentBoard />);

    const card = screen.getByLabelText("Segment: Platform engineers, secrets rotation");
    expect(
      within(card).getByText("Mean opportunity 16.0 across 1 scored · 1 not scored"),
    ).toBeInTheDocument();
    // The unscored member still appears, with no invented score.
    expect(within(card).getByText("N/A")).toBeInTheDocument();
  });

  it("renders Not scored for an all-unscored segment, never a fake zero", () => {
    harness.state.segments = [segment({ outcome_ids: ["O-3"] })];

    render(<SegmentBoard />);

    const card = screen.getByLabelText("Segment: Platform engineers, secrets rotation");
    expect(within(card).getByText("Not scored")).toBeInTheDocument();
    expect(within(card).queryByText("0.0")).toBeNull();
    expect(within(card).queryByText(/NaN/)).toBeNull();
  });

  it("drops a member whose outcome is missing from the canvas and counts it", () => {
    // Three ids, two present outcomes: the third is not invented.
    harness.state.segments = [segment({ outcome_ids: ["O-1", "O-2", "O-404"] })];

    render(<SegmentBoard />);

    const card = screen.getByLabelText("Segment: Platform engineers, secrets rotation");
    const members = within(card).getAllByRole("button", { name: /^Open O-/ });
    expect(members).toHaveLength(2);
    expect(within(card).queryByRole("button", { name: /^Open O-404/ })).toBeNull();
    expect(
      within(card).getByText("1 member outcome(s) are not on the canvas and are not shown."),
    ).toBeInTheDocument();
  });

  it("calls an inferred group a candidate and a named group named", () => {
    harness.state.segments = [
      segment({ id: "SEG-INF", name: "Inferred group", people_inferred: true }),
      segment({ id: "SEG-NAMED", name: "Named group", people_inferred: false }),
    ];

    render(<SegmentBoard />);

    const candidate = screen.getByText(
      "Candidate segment — grouped by the job it serves, not by researched people.",
    );
    expect(candidate).toBeInTheDocument();

    const named = screen.getByLabelText("Segment: Named group");
    expect(within(named).getByText("People named from your evidence.")).toBeInTheDocument();
    expect(
      within(named).queryByText(
        "Candidate segment — grouped by the job it serves, not by researched people.",
      ),
    ).toBeNull();
  });

  it("says there are no segments yet rather than drawing an empty box", () => {
    harness.state.segments = [];

    render(<SegmentBoard />);

    expect(
      screen.getByText("No segments yet — score outcomes to derive them."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Segment:/)).toBeNull();
  });

  it("focuses a member outcome in the landscape when it is clicked", () => {
    harness.state.segments = [segment()];

    render(<SegmentBoard />);
    fireEvent.click(screen.getByRole("button", { name: /^Open O-2:/ }));

    expect(harness.state.focusSubject).toHaveBeenCalledWith("outcome", "O-2");
    expect(harness.state.openPanel).toHaveBeenCalledWith("landscape");
  });

  it("focuses a member outcome with the keyboard, exactly once", () => {
    harness.state.segments = [segment()];

    render(<SegmentBoard />);
    const member = screen.getByRole("button", { name: /^Open O-1:/ });
    fireEvent.keyDown(member, { key: "Enter" });

    expect(harness.state.focusSubject).toHaveBeenCalledTimes(1);
    expect(harness.state.focusSubject).toHaveBeenCalledWith("outcome", "O-1");
  });

  it("keeps the unclustered sentence for outcomes that joined no segment", () => {
    harness.state.segments = [segment({ outcome_ids: ["O-1", "O-2"] })];

    render(<SegmentBoard />);

    expect(
      screen.getByText(
        "Unclustered — 1 outcome(s) joined no segment. One outcome is a hypothesis, not a market.",
      ),
    ).toBeInTheDocument();
  });
});
