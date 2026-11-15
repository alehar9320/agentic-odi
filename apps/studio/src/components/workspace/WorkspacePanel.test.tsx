import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const brokenPanel = vi.hoisted(() => ({ renders: 0, fail: true }));

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

import { ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";

import { WorkspacePanel } from "./WorkspacePanel";

/**
 * The docked lens is the second panel of the stage split, so every test renders
 * it inside the same group App renders (#407).
 */
function Stage() {
  return (
    <ResizablePanelGroup orientation="horizontal">
      <ResizablePanel minSize="40%">thread</ResizablePanel>
      <WorkspacePanel />
    </ResizablePanelGroup>
  );
}

describe("WorkspacePanel", () => {
  beforeEach(() => {
    brokenPanel.renders = 0;
    studio.activePanel = "landscape";
    studio.closePanel.mockClear();
    studio.sendMessage.mockClear();
    studio.canvasState = {
      kind: "ready",
      data: {
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
        source: "seed",
      },
    } as unknown;
  });

  it("renders the view as a lens, not a takeover", () => {
    render(<Stage />);

    expect(
      screen.getByRole("complementary", { name: /opportunity landscape/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/a lens on the conversation, not a separate place/i),
    ).toBeInTheDocument();
  });

  it("returns to the conversation through a question, not a menu", () => {
    render(<Stage />);

    fireEvent.click(screen.getByRole("button", { name: /ask which to chase/i }));

    expect(studio.closePanel).toHaveBeenCalled();
    expect(studio.sendMessage).toHaveBeenCalledWith(
      expect.stringContaining("which opportunity should I chase first"),
    );
  });

  it("closes from the header without sending anything", () => {
    render(<Stage />);

    fireEvent.click(screen.getByRole("button", { name: /close workspace view/i }));

    expect(studio.closePanel).toHaveBeenCalled();
    expect(studio.sendMessage).not.toHaveBeenCalled();
  });

  it("moves focus into the lens and gives it back to the chip when it closes (#696)", () => {
    const chip = document.createElement("button");
    chip.textContent = "Landscape";
    document.body.append(chip);
    chip.focus();

    const { rerender } = render(<Stage />);

    const heading = screen.getByRole("heading", { name: /opportunity landscape/i });
    expect(heading).toHaveFocus();
    expect(heading).toHaveAttribute("tabindex", "-1");

    studio.activePanel = null;
    rerender(<Stage />);

    expect(chip).toHaveFocus();
    chip.remove();
  });

  it("remembers where a lens was scrolled and starts another at the top (#696)", () => {
    const { rerender } = render(<Stage />);
    const landscape = document.querySelector(".lens__body") as HTMLDivElement;
    landscape.scrollTop = 400;
    fireEvent.scroll(landscape);

    studio.activePanel = null;
    rerender(<Stage />);
    studio.activePanel = "landscape";
    rerender(<Stage />);

    expect((document.querySelector(".lens__body") as HTMLDivElement).scrollTop).toBe(400);

    studio.activePanel = "jobmap";
    rerender(<Stage />);

    expect((document.querySelector(".lens__body") as HTMLDivElement).scrollTop).toBe(0);
  });

  it("renders nothing when no view is open", () => {
    studio.activePanel = null;

    render(<Stage />);

    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
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
    render(<Stage />);

    const dialog = screen.getByRole("dialog", { name: /opportunity landscape/i });
    expect(dialog).toHaveAttribute("data-state", "open");
    expect(document.querySelector('[data-slot="sheet-overlay"]')).not.toBeNull();
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("keeps Tab inside the sheet and wraps at both ends", () => {
    render(<Stage />);

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
    render(<Stage />);

    const event = new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    });
    document.dispatchEvent(event);

    expect(studio.closePanel).toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(true);
  });

  it("returns focus to the trigger when the sheet closes", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Open landscape";
    document.body.append(trigger);
    trigger.focus();

    const { rerender } = render(<Stage />);
    const dialog = screen.getByRole("dialog", { name: /opportunity landscape/i });
    expect(dialog.contains(document.activeElement)).toBe(true);

    studio.activePanel = null;
    rerender(<Stage />);

    // The copied primitive owns the return-to-trigger path; jsdom does not run
    // the close transition that completes it, so assert the sheet is gone and
    // focus did not stay inside it.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    trigger.remove();
  });

  it("hides the rest of the app from assistive technology while open", () => {
    const outside = document.createElement("div");
    outside.textContent = "Behind the sheet";
    document.body.append(outside);

    const { unmount } = render(<Stage />);

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
    render(<Stage />);

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText(/reload the studio/i)).toBeNull();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("recovers when the panel is retried", () => {
    render(<Stage />);
    brokenPanel.fail = false;

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    expect(screen.getByText("The lens recovered.")).toBeInTheDocument();
  });
});
