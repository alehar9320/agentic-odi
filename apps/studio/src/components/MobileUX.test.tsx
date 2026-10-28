import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import indexHtml from "../../index.html?raw";
import { StudioProvider, useStudio } from "../state/StudioContext";
import { StudioHeader } from "./StudioHeader";
import { CanvasTabs } from "./canvas/CanvasTabs";
import { ChatCopilot } from "./chat/ChatCopilot";
import { OutcomeCard } from "./canvas/OutcomeCard";
import { SettingsPanel } from "./SettingsPanel";
import type { Outcome } from "../types";

const mockOutcome: Outcome = {
  id: "O-101",
  job_id: "JOB-1",
  statement: "Minimize time required to sync environment secrets",
  importance: 9.2,
  satisfaction: 2.1,
  opportunity_score: 16.3,
  evidence: "Gong transcript #42",
};

function TestTabsWrapper() {
  const { setEngagementLevel } = useStudio();
  return (
    <div>
      <button type="button" onClick={() => setEngagementLevel(2)}>
        Set L2
      </button>
      <CanvasTabs />
    </div>
  );
}

describe("Mobile UX Micro-Improvements", () => {
  it("keeps mobile browser zoom available while using safe-area viewport sizing", () => {
    const viewport = indexHtml.match(/<meta name="viewport" content="([^"]+)"/i)?.[1];

    expect(viewport).toContain("viewport-fit=cover");
    expect(viewport).not.toMatch(/(?:maximum-scale|user-scalable)/i);
  });

  it("renders StudioHeader with title and engagement level buttons", async () => {
    await act(async () => {
      render(
        <StudioProvider>
          <StudioHeader />
        </StudioProvider>
      );
    });

    expect(screen.getByText(/The Living Studio/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Engagement level 0" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Engagement level 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Engagement level 2" })).toBeInTheDocument();
  });

  it("renders CanvasTabs with accessible tablist and tabs when engagement level >= 1", async () => {
    await act(async () => {
      render(
        <StudioProvider>
          <TestTabsWrapper />
        </StudioProvider>
      );
    });

    const setL2Btn = screen.getByRole("button", { name: "Set L2" });
    await act(async () => {
      fireEvent.click(setL2Btn);
    });

    const tabList = screen.getByRole("tablist");
    expect(tabList).toBeInTheDocument();
    const tabs = screen.getAllByRole("tab");
    expect(tabs.length).toBeGreaterThanOrEqual(5);
  });

  it("renders ChatCopilot with mobile FAB and quick prompt pills", async () => {
    await act(async () => {
      render(
        <StudioProvider>
          <ChatCopilot />
        </StudioProvider>
      );
    });

    const fab = screen.getByRole("button", { name: /Open AI Copilot Chat/i });
    expect(fab).toBeInTheDocument();

    const quickPill = screen.getByRole("button", { name: /Define Job/i });
    expect(quickPill).toBeInTheDocument();
  });

  it("renders OutcomeCard with scores and touch-friendly actions", async () => {
    await act(async () => {
      render(
        <StudioProvider>
          <OutcomeCard outcome={mockOutcome} />
        </StudioProvider>
      );
    });

    expect(screen.getByText("O-101")).toBeInTheDocument();
    expect(screen.getByText(/Minimize time required to sync environment secrets/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Simulate/i })).toBeInTheDocument();
  });

  it("expands and collapses SettingsPanel on toggle click", async () => {
    await act(async () => {
      render(
        <StudioProvider>
          <SettingsPanel />
        </StudioProvider>
      );
    });

    const toggleBtn = screen.getByRole("button", { name: /Expand Settings/i });
    expect(toggleBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(toggleBtn);
    });
    expect(screen.getByText("LLM Base URL")).toBeInTheDocument();

    const collapseBtn = screen.getByRole("button", { name: /Collapse/i });
    await act(async () => {
      fireEvent.click(collapseBtn);
    });
    expect(screen.queryByText("LLM Base URL")).not.toBeInTheDocument();
  });
});
