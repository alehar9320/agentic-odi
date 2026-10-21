import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const studio = vi.hoisted(() => ({
  activePanel: "landscape" as string | null,
  closePanel: vi.fn(),
  sendMessage: vi.fn(async () => undefined),
  canvas: {
    jobs: [],
    steps: [],
    outcomes: [
      {
        id: "O-1",
        statement: "Minimize the time it takes to ship",
        importance: 9,
        satisfaction: 3,
        opportunity_score: 15,
      },
    ],
    source: "seed" as const,
  },
  canvasLoading: false,
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

import { WorkspacePanel } from "./WorkspacePanel";

describe("WorkspacePanel", () => {
  beforeEach(() => {
    studio.activePanel = "landscape";
    studio.closePanel.mockClear();
    studio.sendMessage.mockClear();
  });

  it("renders the view as a lens, not a takeover", () => {
    render(<WorkspacePanel />);

    expect(
      screen.getByRole("complementary", { name: /opportunity landscape/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/a lens on the conversation, not a separate place/i),
    ).toBeInTheDocument();
  });

  it("returns to the conversation through a question, not a menu", () => {
    render(<WorkspacePanel />);

    fireEvent.click(screen.getByRole("button", { name: /ask which to chase/i }));

    expect(studio.closePanel).toHaveBeenCalled();
    expect(studio.sendMessage).toHaveBeenCalledWith(
      expect.stringContaining("which opportunity should I chase first"),
    );
  });

  it("closes from the header without sending anything", () => {
    render(<WorkspacePanel />);

    fireEvent.click(screen.getByRole("button", { name: /close workspace view/i }));

    expect(studio.closePanel).toHaveBeenCalled();
    expect(studio.sendMessage).not.toHaveBeenCalled();
  });

  it("renders nothing when no view is open", () => {
    studio.activePanel = null;

    const { container } = render(<WorkspacePanel />);

    expect(container).toBeEmptyDOMElement();
  });
});
