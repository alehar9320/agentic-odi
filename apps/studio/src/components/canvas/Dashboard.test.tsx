import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CanvasData, Signal } from "../../types";
import { Dashboard } from "./Dashboard";

const api = vi.hoisted(() => ({
  fetchStudies: vi.fn<() => Promise<unknown>>(),
}));

vi.mock("../../api/studioApi", () => ({
  fetchStudies: api.fetchStudies,
  asStudioError: (error: unknown) => ({
    code: "unknown",
    message: (error as Error).message ?? "Something went wrong.",
  }),
}));

const harness = vi.hoisted(() => ({
  state: {
    signals: [] as unknown[],
    unreadSignalCount: 0,
    canvas: null as unknown,
    strategy: null as unknown,
    settings: { mcp_url: "http://localhost:8000/mcp" },
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const CANVAS: CanvasData = {
  jobs: [{ id: "JOB-1", name: "Rotate secrets" }],
  steps: [],
  outcomes: [
    {
      id: "O-1",
      job_id: "JOB-1",
      statement: "Minimize the time to rotate a secret",
      importance: 9,
      satisfaction: 2,
      opportunity_score: 16,
    },
    {
      id: "O-2",
      job_id: "JOB-1",
      statement: "Minimize the risk of a stale credential",
      importance: 8,
      satisfaction: 4,
      opportunity_score: null,
    },
  ],
  source: "seed",
};

function signal(overrides: Partial<Signal> = {}): Signal {
  return {
    id: "SIG-1",
    kind: "outcome_scored",
    title: "Scored an outcome",
    severity: "info",
    created_at: new Date().toISOString(),
    suppressed: false,
    fingerprint: "fp-1",
    ...overrides,
  };
}

beforeEach(() => {
  api.fetchStudies.mockReset();
  api.fetchStudies.mockResolvedValue([]);
  harness.state.signals = [];
  harness.state.unreadSignalCount = 0;
  harness.state.canvas = CANVAS;
  harness.state.strategy = null;
});

describe("Dashboard", () => {
  it("shows the five headline cards from real records", async () => {
    harness.state.signals = [signal(), signal({ id: "SIG-2" })];
    harness.state.unreadSignalCount = 3;
    harness.state.strategy = { bets: ["Bet one", "Bet two"] };

    render(<Dashboard />);

    await waitFor(() => expect(api.fetchStudies).toHaveBeenCalled());

    const metrics = screen.getByLabelText("Headline metrics");
    const valueFor = (label: string) =>
      within(metrics).getByText(label).parentElement?.querySelector(".metric__value")?.textContent;
    expect(valueFor("Outcomes scored")).toBe("2");
    expect(valueFor("Signals pending review")).toBe("3");
    expect(valueFor("Studies opened")).toBe("0");
    expect(valueFor("Active strategy bets")).toBe("2");
  });

  it("reads Not scored for an all-unscored board rather than a fake zero", async () => {
    harness.state.canvas = { ...CANVAS, outcomes: [{ id: "O-9", opportunity_score: null }] };

    render(<Dashboard />);

    await waitFor(() => expect(api.fetchStudies).toHaveBeenCalled());
    expect(screen.getByText("Not scored")).toBeInTheDocument();
  });

  it("shows zeros for an empty workspace, never fabricated numbers", async () => {
    harness.state.canvas = { jobs: [], steps: [], outcomes: [], source: "seed" };

    render(<Dashboard />);

    await waitFor(() => expect(api.fetchStudies).toHaveBeenCalled());
    const metrics = screen.getByLabelText("Headline metrics");
    expect(within(metrics).getAllByText("0").length).toBeGreaterThanOrEqual(3);
    expect(within(metrics).getByText("Not scored")).toBeInTheDocument();
  });

  it("re-filters the metrics and the trend when the range changes", async () => {
    // A signal from a month ago is in "All time" but not in "This week".
    const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString();
    harness.state.signals = [
      signal({ id: "old", created_at: monthAgo }),
      signal({ id: "new", created_at: new Date().toISOString() }),
    ];

    render(<Dashboard />);

    await waitFor(() => expect(api.fetchStudies).toHaveBeenCalled());
    // Default range is "This week": only the recent signal counts.
    expect(screen.getByText("1 signals")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "All time" }));

    await waitFor(() => expect(screen.getByText("2 signals")).toBeInTheDocument());
  });

  it("draws an empty axis when an unbounded range has nothing recorded", async () => {
    render(<Dashboard />);

    await waitFor(() => expect(api.fetchStudies).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "All time" }));

    await waitFor(() =>
      expect(
        screen.getByText("No signals recorded in this range yet — the axis is empty."),
      ).toBeInTheDocument(),
    );
  });
});
