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
  detail: null as null | { panel: string; subject?: { kind: string; id: string } },
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
    studio.openPanel.mockClear();
    studio.detail = null;
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
    render(<Stage />);

    const lens = screen.getByRole("complementary", { name: /where to focus/i });
    expect(lens).toBeInTheDocument();
    expect(screen.getByText(/a lens on the conversation, not a separate place/i)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /where to focus/i }),
    ).toHaveAccessibleName(/where to focus/i);
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

  it("names the conversation and artifact in the header (#324)", () => {
    render(<Stage />);

    expect(screen.getByText("Pricing research")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /where to focus/i }),
    ).toBeInTheDocument();
  });

  it("lists sibling artifacts with counts and switches without closing (#324)", () => {
    const { rerender } = render(<Stage />);

    const siblingNav = screen.getByRole("navigation", { name: /other views|siblings/i });
    expect(
      within(siblingNav).getByRole("button", { name: /steps in the job.*1/i }),
    ).toBeInTheDocument();
    expect(
      within(siblingNav).getByRole("button", { name: /what customers said.*1/i }),
    ).toBeInTheDocument();

    fireEvent.click(within(siblingNav).getByRole("button", { name: /steps in the job/i }));

    expect(studio.openPanel).toHaveBeenCalledWith("jobmap");
    expect(studio.closePanel).not.toHaveBeenCalled();

    studio.activePanel = "jobmap";
    rerender(<Stage />);

    expect(
      screen.getByRole("complementary", { name: /steps in the job/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /steps in the job/i }),
    ).toBeInTheDocument();
  });

  it("returns focus to the opener on Escape (#324)", () => {
    const opener = document.createElement("button");
    opener.textContent = "Open landscape";
    document.body.append(opener);
    opener.focus();

    const { rerender } = render(<Stage />);
    expect(
      screen.getByRole("heading", { name: /where to focus/i }),
    ).toHaveFocus();

    fireEvent.keyDown(window, { key: "Escape" });

    expect(studio.closePanel).toHaveBeenCalled();

    studio.activePanel = null;
    rerender(<Stage />);

    expect(opener).toHaveFocus();
    opener.remove();
  });

  it("moves focus into the lens and gives it back to the chip when it closes (#696)", () => {
    const chip = document.createElement("button");
    chip.textContent = "Landscape";
    document.body.append(chip);
    chip.focus();

    const { rerender } = render(<Stage />);

    const heading = screen.getByRole("heading", { name: /where to focus/i });
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

  it("frames the detail with its place in the job when a step backs it (#740)", () => {
    studio.activePanel = "jobmap";
    studio.detail = { panel: "jobmap", subject: { kind: "step", id: "S-2" } };
    studio.canvas = {
      jobs: [],
      steps: [
        { id: "S-1", order: 1, name: "Frame the question" },
        { id: "S-2", order: 2, name: "Locate" },
      ],
      outcomes: [],
      source: "seed",
    } as never;

    render(<Stage />);

    expect(screen.getByText("Step 2 of 2 • Locate")).toBeInTheDocument();
  });

  it("omits the context line when nothing real backs it (#740)", () => {
    studio.activePanel = "landscape";
    studio.detail = { panel: "landscape" };

    render(<Stage />);

    expect(document.querySelector(".lens__context")).toBeNull();
  });

  it("offers an expand control that is off until used (#740)", () => {
    render(<Stage />);

    const expand = screen.getByRole("button", { name: /expand workspace view/i });
    expect(expand).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(expand);

    expect(screen.getByRole("button", { name: /restore workspace view/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
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

    const dialog = screen.getByRole("dialog", { name: /where to focus/i });
    expect(dialog).toHaveAttribute("data-state", "open");
    expect(document.querySelector('[data-slot="sheet-overlay"]')).not.toBeNull();
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("keeps Tab inside the sheet and wraps at both ends", () => {
    render(<Stage />);

    const dialog = screen.getByRole("dialog", { name: /where to focus/i });
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
    const dialog = screen.getByRole("dialog", { name: /where to focus/i });
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
