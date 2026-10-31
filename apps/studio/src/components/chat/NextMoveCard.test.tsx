import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CanvasData, ChatMessage, Signal, StudioBrief } from "../../types";

const studio = vi.hoisted(() => ({
  brief: null as StudioBrief | null,
  messages: [] as ChatMessage[],
  canvas: null as CanvasData | null,
  signals: [] as Signal[],
  theses: [],
  llmHealth: { healthy: true as boolean | null, message: "" },
  openSetup: vi.fn(),
  openPanel: vi.fn(),
  sendMessage: vi.fn(async () => undefined),
}));

vi.mock("../../state/StudioContext", () => ({ useStudio: () => studio }));

const { NextMoveCard } = await import("./NextMoveCard");

const REPLY: ChatMessage = {
  id: "a-1",
  parentId: "u-1",
  role: "assistant",
  content: "Scored it.",
  parts: [],
};

const BRIEF: StudioBrief = {
  product_name: "Ambient",
  target_user: "platform engineers",
  job_statement: "Ship a service",
  core_problem: "Config drift",
  job_id: "job-1",
};

function renderCard() {
  return render(<NextMoveCard />);
}

beforeEach(() => {
  studio.brief = null;
  studio.messages = [REPLY];
  studio.canvas = null;
  studio.signals = [];
  studio.theses = [];
  studio.llmHealth = { healthy: true, message: "" };
  studio.openSetup.mockClear();
  studio.openPanel.mockClear();
  studio.sendMessage.mockClear();
});

describe("NextMoveCard", () => {
  it("renders nothing before the first assistant turn", () => {
    studio.messages = [{ id: "u-1", parentId: null, role: "user", content: "hi" }];
    renderCard();
    expect(screen.queryByRole("complementary", { name: "Recommended next move" })).toBeNull();
  });

  it("opens context from the card", () => {
    renderCard();
    expect(
      screen.getByText("Tell the studio what you are building."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add context" }));
    expect(studio.openSetup).toHaveBeenCalledTimes(1);
  });

  it("opens the named lens for a signal", () => {
    studio.brief = BRIEF;
    studio.signals = [
      {
        id: "s-1",
        kind: "opportunity_crossed",
        title: "Invoices crossed the threshold",
        severity: "urgent",
        created_at: "2026-10-31T09:00:00Z",
        fingerprint: "s-1",
        suppressed: false,
      },
    ];
    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Open Catch Up" }));
    expect(studio.openPanel).toHaveBeenCalledWith("catchup");
  });

  it("dismisses this move only", () => {
    renderCard();
    fireEvent.click(
      screen.getByRole("button", { name: "Dismiss this recommendation" }),
    );
    expect(screen.queryByRole("complementary", { name: "Recommended next move" })).toBeNull();
  });
});
