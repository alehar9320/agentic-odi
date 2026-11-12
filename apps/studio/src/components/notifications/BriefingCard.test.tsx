import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Briefing } from "../../types";
import { BRIEFING_DISMISSED_KEY } from "../../lib/briefingDismissed";
import { BriefingCard } from "./BriefingCard";

const mocks = vi.hoisted(() => ({
  fetchLatestBriefing: vi.fn(),
  openRecord: vi.fn(),
}));

vi.mock("../../api/studioApi", () => ({
  fetchLatestBriefing: mocks.fetchLatestBriefing,
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({ openRecord: mocks.openRecord }),
}));

function briefing(overrides: Partial<Briefing> = {}): Briefing {
  return {
    run_id: "work-1",
    created_at: new Date().toISOString(),
    items: [
      { kind: "added", text: "A new quote mentions onboarding.", record_id: "ev-1", record_kind: "evidence" },
      { kind: "changed", text: "O-12 rose to 14.2.", record_id: "o-12", record_kind: "outcome" },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("BriefingCard", () => {
  it("renders nothing before a run has finished", async () => {
    mocks.fetchLatestBriefing.mockResolvedValue(null);
    const { container } = render(<BriefingCard />);

    await waitFor(() => expect(mocks.fetchLatestBriefing).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("shows one line per change and links each to its record", async () => {
    mocks.fetchLatestBriefing.mockResolvedValue(briefing());
    render(<BriefingCard />);

    expect(await screen.findByRole("heading", { name: "Since you were away" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "O-12 rose to 14.2." }));
    expect(mocks.openRecord).toHaveBeenCalledWith("outcome", "o-12");
  });

  it("activates each displayed line through openRecord with its record id", async () => {
    mocks.fetchLatestBriefing.mockResolvedValue(
      briefing({
        items: [
          { kind: "added", text: "First.", record_id: "ev-1", record_kind: "evidence" },
          { kind: "changed", text: "Second.", record_id: "o-12", record_kind: "outcome" },
          { kind: "failed", text: "Third.", record_id: "sw-3", record_kind: "agent_work" },
        ],
      }),
    );
    render(<BriefingCard />);

    // agent_work cannot be opened, so only the two openable lines render.
    expect(await screen.findAllByRole("listitem")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "First." }));
    expect(mocks.openRecord).toHaveBeenCalledWith("evidence", "ev-1");

    fireEvent.click(screen.getByRole("button", { name: "Second." }));
    expect(mocks.openRecord).toHaveBeenCalledWith("outcome", "o-12");
  });

  it("renders at most four items", async () => {
    mocks.fetchLatestBriefing.mockResolvedValue(
      briefing({
        items: [
          { kind: "added", text: "One.", record_id: "r-1", record_kind: "evidence" },
          { kind: "changed", text: "Two.", record_id: "r-2", record_kind: "outcome" },
          { kind: "failed", text: "Three.", record_id: "r-3", record_kind: "segment" },
          { kind: "added", text: "Four.", record_id: "r-4", record_kind: "strategy" },
          { kind: "changed", text: "Five.", record_id: "r-5", record_kind: "job" },
        ],
      }),
    );
    render(<BriefingCard />);

    expect(await screen.findAllByRole("listitem")).toHaveLength(4);
    expect(screen.queryByRole("button", { name: "Five." })).toBeNull();
  });

  it("says so plainly when the run changed nothing", async () => {
    mocks.fetchLatestBriefing.mockResolvedValue(briefing({ items: [] }));
    render(<BriefingCard />);

    expect(await screen.findByText(/found nothing that needs your attention/i)).toBeInTheDocument();
    expect(screen.queryByRole("listitem")).toBeNull();
  });

  it("does not render a line whose record kind cannot be opened", async () => {
    mocks.fetchLatestBriefing.mockResolvedValue(
      briefing({
        items: [{ kind: "failed", text: "A connector timed out.", record_id: "c-1", record_kind: "connector" }],
      }),
    );
    render(<BriefingCard />);

    expect(screen.queryByText("A connector timed out.")).toBeNull();
    expect(screen.queryByRole("button", { name: "A connector timed out." })).toBeNull();
  });

  it("stays hidden once dismissed and remembers that across a remount", async () => {
    const shown = briefing();
    mocks.fetchLatestBriefing.mockResolvedValue(shown);
    const first = render(<BriefingCard />);

    fireEvent.click(await screen.findByRole("button", { name: "Dismiss" }));
    expect(first.container).toBeEmptyDOMElement();
    const dismissed = JSON.parse(localStorage.getItem(BRIEFING_DISMISSED_KEY) ?? "[]");
    expect(dismissed).toContain(`work-1:${shown.created_at}`);

    const second = render(<BriefingCard />);
    await waitFor(() => expect(mocks.fetchLatestBriefing).toHaveBeenCalledTimes(2));
    expect(second.container).toBeEmptyDOMElement();
  });
});
