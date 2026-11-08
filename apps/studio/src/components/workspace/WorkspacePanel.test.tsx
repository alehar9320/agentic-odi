import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const brokenPanel = vi.hoisted(() => ({ renders: 0, fail: true }));

const studio = vi.hoisted(() => ({
  activePanel: "landscape" as string | null,
  openPanel: vi.fn(),
  closePanel: vi.fn(),
  sendMessage: vi.fn(async () => undefined),
  conversationId: "c1",
  conversations: [{ id: "c1", title: "Pricing research", turn_count: 2 }],
  memory: [],
  segments: [],
  canvas: {
    jobs: [{ id: "J-1", name: "Ship" }],
    steps: [{ id: "S-1", job_id: "J-1", name: "Plan", order: 1 }],
    outcomes: [
      {
        id: "O-1",
        job_id: "J-1",
        statement: "Minimize the time it takes to ship",
        importance: 9,
        satisfaction: 3,
        opportunity_score: 15,
        evidence: "quote",
      },
    ],
    source: "seed" as const,
  },
  canvasLoading: false,
  canvasState: { kind: "ready", data: null } as unknown,
  canvasError: null,
  refreshCanvas: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

vi.mock("./panels", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./panels")>();
  return {
    ...actual,
    findPanel: (id: string) => {
      if (id !== "broken") {
        return actual.findPanel(id as never);
      }
      return {
        id: "broken" as never,
        label: "Broken",
        title: "Broken lens",
        blurb: "A lens that throws.",
        icon: null,
        render: () => {
          brokenPanel.renders += 1;
          if (brokenPanel.fail) {
            throw new Error("the lens exploded");
          }
          return <p>The lens recovered.</p>;
        },
      };
    },
  };
});

import { WorkspacePanel } from "./WorkspacePanel";

describe("WorkspacePanel", () => {
  beforeEach(() => {
    brokenPanel.renders = 0;
    studio.activePanel = "landscape";
    studio.openPanel.mockClear();
    studio.closePanel.mockClear();
    studio.sendMessage.mockClear();
    studio.conversationId = "c1";
    studio.conversations = [{ id: "c1", title: "Pricing research", turn_count: 2 }];
    studio.canvasState = {
      kind: "ready",
      data: {
        jobs: [{ id: "J-1", name: "Ship" }],
        steps: [{ id: "S-1", job_id: "J-1", name: "Plan", order: 1 }],
        outcomes: [
          {
            id: "O-1",
            job_id: "J-1",
            statement: "Minimize the time it takes to ship",
            importance: 9,
            satisfaction: 3,
            opportunity_score: 15,
            evidence: "quote",
          },
        ],
        source: "seed",
      },
    } as unknown;
  });

  it("renders the view as a lens, not a takeover", () => {
    render(<WorkspacePanel />);

    const lens = screen.getByRole("complementary", { name: /opportunity landscape/i });
    expect(lens).toBeInTheDocument();
    expect(screen.getByText(/a lens on the conversation, not a separate place/i)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /opportunity landscape/i }),
    ).toHaveAccessibleName(/opportunity landscape/i);
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

  it("names the conversation and artifact in the header (#324)", () => {
    render(<WorkspacePanel />);

    expect(screen.getByText("Pricing research")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /opportunity landscape/i }),
    ).toBeInTheDocument();
  });

  it("lists sibling artifacts with counts and switches without closing (#324)", () => {
    const { rerender } = render(<WorkspacePanel />);

    const siblingNav = screen.getByRole("navigation", { name: /other views|siblings/i });
    expect(within(siblingNav).getByRole("button", { name: /job map.*1/i })).toBeInTheDocument();
    expect(within(siblingNav).getByRole("button", { name: /evidence.*1/i })).toBeInTheDocument();

    fireEvent.click(within(siblingNav).getByRole("button", { name: /job map/i }));

    expect(studio.openPanel).toHaveBeenCalledWith("jobmap");
    expect(studio.closePanel).not.toHaveBeenCalled();

    studio.activePanel = "jobmap";
    rerender(<WorkspacePanel />);

    expect(
      screen.getByRole("complementary", { name: /universal job map/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /universal job map/i }),
    ).toBeInTheDocument();
  });

  it("returns focus to the opener on Escape (#324)", () => {
    const opener = document.createElement("button");
    opener.textContent = "Open landscape";
    document.body.append(opener);
    opener.focus();

    const { rerender } = render(<WorkspacePanel />);
    expect(
      screen.getByRole("heading", { name: /opportunity landscape/i }),
    ).toHaveFocus();

    fireEvent.keyDown(window, { key: "Escape" });

    expect(studio.closePanel).toHaveBeenCalled();

    studio.activePanel = null;
    rerender(<WorkspacePanel />);

    expect(opener).toHaveFocus();
    opener.remove();
  });

  it("moves focus into the lens and gives it back to the chip when it closes (#696)", () => {
    const chip = document.createElement("button");
    chip.textContent = "Landscape";
    document.body.append(chip);
    chip.focus();

    const { rerender } = render(<WorkspacePanel />);

    const heading = screen.getByRole("heading", { name: /opportunity landscape/i });
    expect(heading).toHaveFocus();
    expect(heading).toHaveAttribute("tabindex", "-1");

    studio.activePanel = null;
    rerender(<WorkspacePanel />);

    expect(chip).toHaveFocus();
    chip.remove();
  });

  it("remembers where a lens was scrolled and starts another at the top (#696)", () => {
    const { rerender } = render(<WorkspacePanel />);
    const landscape = document.querySelector(".lens__body") as HTMLDivElement;
    landscape.scrollTop = 400;
    fireEvent.scroll(landscape);

    studio.activePanel = null;
    rerender(<WorkspacePanel />);
    studio.activePanel = "landscape";
    rerender(<WorkspacePanel />);

    expect((document.querySelector(".lens__body") as HTMLDivElement).scrollTop).toBe(400);

    studio.activePanel = "jobmap";
    rerender(<WorkspacePanel />);

    expect((document.querySelector(".lens__body") as HTMLDivElement).scrollTop).toBe(0);
  });

  it("renders nothing when no view is open", () => {
    studio.activePanel = null;

    const { container } = render(<WorkspacePanel />);

    expect(container).toBeEmptyDOMElement();
  });
});

describe("WorkspacePanel as a mobile sheet", () => {
  const originalMatchMedia = window.matchMedia;

  beforeEach(() => {
    studio.activePanel = "landscape";
    studio.closePanel.mockClear();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: (query: string) => ({
        matches: query === "(max-width: 1023px)",
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }),
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: originalMatchMedia,
    });
  });

  it("opens as a modal dialog with focus inside it", () => {
    render(<WorkspacePanel />);

    const dialog = screen.getByRole("dialog", { name: /opportunity landscape/i });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("keeps Tab inside the sheet and wraps at both ends", () => {
    render(<WorkspacePanel />);

    const dialog = screen.getByRole("dialog", { name: /opportunity landscape/i });
    const buttons = within(dialog).getAllByRole("button");
    const first = buttons[0];
    const last = buttons[buttons.length - 1];

    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(first).toHaveFocus();

    first.focus();
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
  });

  it("closes on Escape before the app's global handler can stop a reply", () => {
    render(<WorkspacePanel />);

    const event = new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    });
    const stopped = vi.fn();
    window.addEventListener("keydown", stopped);
    window.dispatchEvent(event);
    window.removeEventListener("keydown", stopped);

    expect(studio.closePanel).toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(true);
    expect(stopped).not.toHaveBeenCalled();
  });

  it("returns focus to the trigger when the sheet closes", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Open landscape";
    document.body.append(trigger);
    trigger.focus();

    const { rerender } = render(<WorkspacePanel />);
    expect(trigger).not.toHaveFocus();

    studio.activePanel = null;
    rerender(<WorkspacePanel />);

    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("hides the rest of the app from assistive technology while open", () => {
    const outside = document.createElement("div");
    outside.textContent = "Behind the sheet";
    document.body.append(outside);

    const { unmount } = render(<WorkspacePanel />);

    expect(outside).toHaveAttribute("aria-hidden", "true");

    unmount();

    expect(outside).not.toHaveAttribute("aria-hidden");
    outside.remove();
  });
});

describe("WorkspacePanel with a broken lens", () => {
  beforeEach(() => {
    brokenPanel.renders = 0;
    brokenPanel.fail = true;
    studio.activePanel = "broken";
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("contains the failure to the panel instead of the whole studio", () => {
    render(<WorkspacePanel />);

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText(/reload the studio/i)).toBeNull();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("recovers when the panel is retried", () => {
    render(<WorkspacePanel />);
    brokenPanel.fail = false;

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    expect(screen.getByText("The lens recovered.")).toBeInTheDocument();
  });
});
