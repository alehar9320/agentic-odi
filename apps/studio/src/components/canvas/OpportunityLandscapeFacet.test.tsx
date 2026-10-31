import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchAlternativeLinks } from "../../api/studioApi";
import type { CanvasState } from "../../types";
import { OpportunityLandscape } from "./OpportunityLandscape";

vi.mock("../../api/studioApi", () => ({
  fetchOutcomeHistory: vi.fn().mockResolvedValue([]),
  fetchOutcomeInterval: vi.fn().mockResolvedValue({ outcome_id: "", band: null }),
  fetchOutcomeAlternatives: vi.fn().mockResolvedValue([]),
  fetchExistingSolution: vi.fn().mockResolvedValue("no_link_at_all"),
  fetchAlternativeLinks: vi.fn(),
}));

const canvasData = {
  jobs: [{ id: "JOB-1", name: "Deploy Service" }],
  steps: [],
  outcomes: [
    {
      id: "O-101",
      job_id: "JOB-1",
      statement: "Minimize time spent syncing secrets",
      importance: 9,
      satisfaction: 2,
      opportunity_score: 16,
    },
    {
      id: "O-102",
      job_id: "JOB-1",
      statement: "Minimize risk of configuration drift",
      importance: 8,
      satisfaction: 7,
      opportunity_score: 9,
    },
  ],
  source: "seed" as const,
};

const harness = vi.hoisted(() => ({
  state: {
    canvasState: { kind: "ready", data: null } as unknown as CanvasState,
    refreshCanvas: vi.fn(),
    openPanel: vi.fn(),
    pushToast: vi.fn(),
    theses: [],
    deleteThesis: vi.fn(),
    settings: { mcp_url: "http://localhost:8000/mcp" },
    focusedSubject: null as { kind: string; id: string } | null,
    focusSubject: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const links = vi.mocked(fetchAlternativeLinks);

function link(outcome_id: string, kind: string, name = "Thing") {
  return {
    outcome_id,
    alternative: { id: `A-${outcome_id}`, job_id: "JOB-1", name, kind },
    link: { outcome_id, alternative_id: `A-${outcome_id}`, adequacy: 5.0, usage_n: null, note: null },
  };
}

describe("OpportunityLandscape workaround facet", () => {
  beforeEach(() => {
    harness.state.canvasState = { kind: "ready", data: canvasData } as unknown as CanvasState;
    links.mockReset();
  });

  it("filters to outcomes whose only recorded solution is a workaround", async () => {
    links.mockResolvedValue([link("O-101", "workaround", "Homegrown script")] as never);

    render(<OpportunityLandscape />);
    fireEvent.click(screen.getByText("🎴 Visual Cards"));
    fireEvent.click(screen.getByTestId("facet-only-workaround"));

    await waitFor(() =>
      expect(screen.queryByText("Minimize risk of configuration drift")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Minimize time spent syncing secrets")).toBeInTheDocument();
  });

  it("does not treat a non-workaround solution as only-workaround", async () => {
    links.mockResolvedValue([link("O-101", "product", "Competitor")] as never);

    render(<OpportunityLandscape />);
    fireEvent.click(screen.getByText("🎴 Visual Cards"));
    fireEvent.click(screen.getByTestId("facet-only-workaround"));

    await waitFor(() =>
      expect(
        screen.getByText("No opportunities match the current filter criteria."),
      ).toBeInTheDocument(),
    );
  });

  it("does not treat a nothing row as a workaround", async () => {
    links.mockResolvedValue([link("O-101", "nothing", "Nothing today")] as never);

    render(<OpportunityLandscape />);
    fireEvent.click(screen.getByText("🎴 Visual Cards"));
    fireEvent.click(screen.getByTestId("facet-only-workaround"));

    await waitFor(() =>
      expect(
        screen.getByText("No opportunities match the current filter criteria."),
      ).toBeInTheDocument(),
    );
  });

  it("does not treat a missing inventory as a workaround", async () => {
    links.mockResolvedValue([]);

    render(<OpportunityLandscape />);
    fireEvent.click(screen.getByText("🎴 Visual Cards"));
    fireEvent.click(screen.getByTestId("facet-only-workaround"));

    await waitFor(() =>
      expect(
        screen.getByText("No opportunities match the current filter criteria."),
      ).toBeInTheDocument(),
    );
  });

  it("excludes a mixed outcome when a non-workaround solution is also recorded", async () => {
    links.mockResolvedValue([
      link("O-101", "workaround", "Homegrown script"),
      link("O-101", "product", "Competitor"),
    ] as never);

    render(<OpportunityLandscape />);
    fireEvent.click(screen.getByText("🎴 Visual Cards"));
    fireEvent.click(screen.getByTestId("facet-only-workaround"));

    await waitFor(() =>
      expect(
        screen.getByText("No opportunities match the current filter criteria."),
      ).toBeInTheDocument(),
    );
  });

  it("disables the facet and says why when the read fails", async () => {
    links.mockRejectedValue(new Error("boom"));

    render(<OpportunityLandscape />);

    await waitFor(() => expect(screen.getByTestId("facet-only-workaround")).toBeDisabled());
  });
});
