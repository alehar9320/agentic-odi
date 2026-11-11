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

  it("says so plainly when the run changed nothing", async () => {
    mocks.fetchLatestBriefing.mockResolvedValue(briefing({ items: [] }));
    render(<BriefingCard />);

    expect(await screen.findByText(/found nothing that needs your attention/i)).toBeInTheDocument();
    expect(screen.queryByRole("listitem")).toBeNull();
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

  it("shows a failed change as plain text when the record kind cannot be opened", async () => {
    mocks.fetchLatestBriefing.mockResolvedValue(
      briefing({
        items: [{ kind: "failed", text: "A connector timed out.", record_id: "c-1", record_kind: "connector" }],
      }),
    );
    render(<BriefingCard />);

    expect(await screen.findByText("A connector timed out.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "A connector timed out." })).toBeNull();
  });
});
