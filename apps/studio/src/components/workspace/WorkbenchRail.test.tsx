import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/** The slice of a canvas the map reads, so a test can hand it only what it means to. */
type CanvasStub = {
  jobs: { id: string }[];
  steps: { id: string; job_id?: string }[];
  outcomes: { id: string; evidence?: string }[];
  evidence?: { id: string }[];
  source: "seed" | "mcp" | "local";
  provenance?: {
    kind: "live" | "seed" | "empty";
    reason: string;
    generated_at: string;
    record_counts: { jobs: number; steps: number; outcomes: number; evidence: number };
  };
};

const studio = vi.hoisted(() => ({
  canvas: null as CanvasStub | null,
  memory: [] as { id: string; text: string; status?: string }[],
  segments: [] as { id: string }[],
  signals: [] as { id: string }[],
  unreadSignalCount: 0,
  activePanel: null as string | null,
  openPanel: vi.fn(),
  closePanel: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

import { WorkbenchRail } from "./WorkbenchRail";
import { SETTINGS_PANEL, WORKSPACE_PANELS } from "./panels";

function canvas(overrides: Partial<CanvasStub> = {}): CanvasStub {
  return {
    jobs: [],
    steps: [],
    outcomes: [],
    source: "seed" as const,
    ...overrides,
  };
}

/** The map in the order it renders: the registry, then Settings at the end. */
const DESTINATIONS: string[] = [...WORKSPACE_PANELS.map((panel) => panel.id), SETTINGS_PANEL.id];

function labelFor(id: string): string {
  return [...WORKSPACE_PANELS, SETTINGS_PANEL].find((panel) => panel.id === id)?.label ?? id;
}

function map(): HTMLElement {
  return screen.getByRole("navigation", { name: "Studio" });
}

const originalMatchMedia = window.matchMedia;

/** Make the media queries in the component answer as if the window were `width` px. */
function matchWidths(width: number): void {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => {
      const limit = Number(/max-width:\s*(\d+)px/.exec(query)?.[1] ?? Number.NaN);
      return {
        matches: Number.isFinite(limit) && width <= limit,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
      };
    },
  });
}

function restoreMatchMedia(): void {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: originalMatchMedia,
  });
}

function rowNames(): string[] {  const nav = screen.getByRole("navigation", { name: "Studio" });
  return Array.from(nav.querySelectorAll<HTMLButtonElement>(".rail__row")).map(
    (row) => row.getAttribute("aria-label") ?? row.textContent ?? "",
  );
}

function seedProvenance(studioCanvas: CanvasStub): CanvasStub {  return {
    ...studioCanvas,
    provenance: {
      kind: "seed" as const,
      reason: "demo" as const,
      generated_at: "2026-10-29T10:00:00+00:00",
      record_counts: { jobs: 0, steps: 0, outcomes: 0, evidence: 0 },
    },
  };
}

describe("WorkbenchRail", () => {
  beforeEach(() => {
    studio.canvas = null;
    studio.memory = [];
    studio.segments = [];
    studio.signals = [];
    studio.unreadSignalCount = 0;
    studio.activePanel = null;
    studio.openPanel.mockClear();
    studio.closePanel.mockClear();
    window.localStorage.clear();
    restoreMatchMedia();
  });

  // The premise of #310: the map is the thing a newcomer uses when there is
  // nothing in the repository yet, so it cannot be the thing that hides.
  it("offers every destination before the thread has made anything", () => {
    studio.canvas = canvas();

    render(<WorkbenchRail />);

    expect(rowNames()).toHaveLength(DESTINATIONS.length);
    expect(screen.getByRole("button", { name: "Records, 0 records" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Capture" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Settings" })).toBeInTheDocument();
  });

  it("stays on screen when the repository has never been read", () => {
    studio.canvas = null;

    render(<WorkbenchRail />);

    expect(screen.getByRole("navigation", { name: "Studio" })).toBeInTheDocument();
    expect(rowNames()).toHaveLength(DESTINATIONS.length);
  });

  it("names each destination the registry declares, in the registry's order", () => {
    studio.canvas = canvas();

    render(<WorkbenchRail />);

    const ids = Array.from(
      screen.getByRole("navigation", { name: "Studio" }).querySelectorAll<HTMLButtonElement>(
        ".rail__row",
      ),
    ).map((row) => row.dataset.panel);

    expect(ids).toEqual(DESTINATIONS);
  });

  it("opens every destination from its row", () => {
    studio.canvas = canvas();

    render(<WorkbenchRail />);

    for (const id of DESTINATIONS) {
      fireEvent.click(screen.getByRole("button", { name: new RegExp(`^${labelFor(id)}`, "i") }));
      expect(studio.openPanel).toHaveBeenLastCalledWith(id);
    }
  });

  it("keeps zero honest, because zero is information", () => {
    studio.canvas = canvas({ outcomes: [], steps: [] });

    render(<WorkbenchRail />);

    expect(screen.getByRole("button", { name: "Landscape, 0 opportunities" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Job map, 0 steps" })).toBeInTheDocument();
  });

  it("caps a count it cannot show rather than lying about it", () => {
    studio.canvas = canvas({
      outcomes: Array.from({ length: 104 }, (_unused, index) => ({ id: `O-${index}` })),
    });

    render(<WorkbenchRail />);

    expect(screen.getByRole("button", { name: "Landscape, 99+ opportunities" })).toBeInTheDocument();
  });

  it("marks the open destination and moves the mark when it changes", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });

    const { rerender } = render(<WorkbenchRail />);
    const row = (id: string) =>
      screen.getByRole("navigation", { name: "Studio" }).querySelector(`[data-panel="${id}"]`);

    expect(row("records")).not.toHaveAttribute("aria-current");

    fireEvent.click(screen.getByRole("button", { name: /^landscape/i }));
    expect(studio.openPanel).toHaveBeenCalledWith("landscape");

    studio.activePanel = "landscape";
    rerender(<WorkbenchRail />);
    expect(row("landscape")).toHaveAttribute("aria-current", "page");

    studio.activePanel = "settings";
    rerender(<WorkbenchRail />);
    expect(row("landscape")).not.toHaveAttribute("aria-current");
    expect(row("settings")).toHaveAttribute("aria-current", "page");
  });

  it("closes the destination a row already points at", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });
    studio.activePanel = "landscape";

    render(<WorkbenchRail />);
    fireEvent.click(screen.getByRole("button", { name: /^landscape/i }));

    expect(studio.closePanel).toHaveBeenCalled();
    expect(studio.openPanel).not.toHaveBeenCalled();
  });

  it("shows what the data is made of from the header, not from a row", () => {
    studio.canvas = seedProvenance(canvas());

    render(<WorkbenchRail />);

    expect(screen.getByRole("navigation", { name: "Studio" })).toContainElement(
      screen.getByText("DEMO"),
    );
  });

  it("derives its items and counts from the canvas", () => {
    studio.canvas = canvas({
      outcomes: [{ id: "O-1", evidence: "a quote" }, { id: "O-2" }],
      steps: [{ id: "S-1" }],
    });

    render(<WorkbenchRail />);

    expect(screen.getByRole("button", { name: "Landscape, 2 opportunities" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Job map, 1 step" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Evidence, 0 quotes" })).toBeInTheDocument();
  });

  it("shows what the agent has learned once it has a note", () => {
    studio.canvas = canvas();
    studio.memory = [
      { id: "o-1", text: "Owns activation." },
      { id: "o-2", text: "Prefers short updates." },
    ];

    render(<WorkbenchRail />);

    fireEvent.click(screen.getByRole("button", { name: "What I know, 2 notes" }));
    expect(studio.openPanel).toHaveBeenCalledWith("memory");
  });

  it("counts the segments the outcomes support", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }, { id: "O-2" }] });
    studio.segments = [{ id: "seg-1" }, { id: "seg-2" }, { id: "seg-3" }];

    render(<WorkbenchRail />);

    fireEvent.click(screen.getByRole("button", { name: "Segments, 3 segments" }));
    expect(studio.openPanel).toHaveBeenCalledWith("segments");
  });

  it("counts the evidence the panel will list, not the outcomes that have a note", () => {
    studio.canvas = canvas({
      outcomes: [
        { id: "O-1", evidence: "a quote" },
        { id: "O-2", evidence: "another" },
        { id: "O-3", evidence: "a third" },
      ],
      evidence: Array.from({ length: 12 }, (_unused, index) => ({ id: `E-${index}` })),
    });

    render(<WorkbenchRail />);

    expect(screen.getByRole("button", { name: "Evidence, 12 quotes" })).toBeInTheDocument();
  });

  it("counts the steps of the job the map opens on", () => {
    studio.canvas = canvas({
      jobs: [{ id: "J-1" }, { id: "J-2" }],
      steps: [
        { id: "S-1", job_id: "J-1" },
        { id: "S-2", job_id: "J-1" },
        { id: "S-3", job_id: "J-2" },
      ],
    });

    render(<WorkbenchRail />);

    expect(screen.getByRole("button", { name: "Job map, 2 steps" })).toBeInTheDocument();
  });

  it("labels a seed canvas as sample data", () => {
    studio.canvas = canvas({
      outcomes: [{ id: "O-1" }],
      provenance: {
        kind: "seed",
        reason: "mcp_unreachable",
        generated_at: "2026-10-29T10:00:00+00:00",
        record_counts: { jobs: 1, steps: 8, outcomes: 5, evidence: 0 },
      },
    });

    render(<WorkbenchRail />);

    expect(screen.getByText("OFFLINE")).toBeInTheDocument();
  });

  it("labels a demo seed differently from an unreachable server", () => {
    studio.canvas = canvas({
      outcomes: [{ id: "O-1" }],
      provenance: {
        kind: "seed",
        reason: "demo",
        generated_at: "2026-10-29T10:00:00+00:00",
        record_counts: { jobs: 1, steps: 8, outcomes: 5, evidence: 0 },
      },
    });

    render(<WorkbenchRail />);

    expect(screen.getByText("DEMO")).toBeInTheDocument();
    expect(screen.queryByText("OFFLINE")).toBeNull();
  });

  it("shows no provenance chip for a live canvas", () => {
    studio.canvas = canvas({
      source: "mcp",
      outcomes: [{ id: "O-1" }],
      provenance: {
        kind: "live",
        reason: "mcp_live",
        generated_at: "2026-10-29T10:00:00+00:00",
        record_counts: { jobs: 1, steps: 1, outcomes: 1, evidence: 0 },
      },
    });

    render(<WorkbenchRail />);

    expect(screen.queryByText("DEMO")).toBeNull();
    expect(screen.queryByText("OFFLINE")).toBeNull();
  });

  it("counts every stored record, not only the outcomes with a note", () => {
    studio.canvas = canvas({
      jobs: [{ id: "J-1" }],
      steps: [{ id: "S-1" }],
      outcomes: [{ id: "O-1" }, { id: "O-2", evidence: "a quote" }],
      evidence: [{ id: "E-1" }],
    });

    render(<WorkbenchRail />);

    expect(screen.getByRole("button", { name: "Records, 5 records" })).toBeInTheDocument();
  });

  it("opens the records lens from its chip", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });

    render(<WorkbenchRail />);

    fireEvent.click(screen.getByRole("button", { name: "Records, 1 record" }));
    expect(studio.openPanel).toHaveBeenCalledWith("records");
  });

  it("opens a view and closes it again from the same chip", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });

    const { rerender } = render(<WorkbenchRail />);
    fireEvent.click(screen.getByRole("button", { name: /^landscape/i }));

    expect(studio.openPanel).toHaveBeenCalledWith("landscape");

    studio.activePanel = "landscape";
    rerender(<WorkbenchRail />);

    const chip = screen.getByRole("button", { name: /^landscape/i });
    expect(chip).toHaveAttribute("aria-current", "page");
    fireEvent.click(chip);

    expect(studio.closePanel).toHaveBeenCalled();
  });

  it("collapses to icons on Cmd/Ctrl+B and writes the choice down", () => {
    studio.canvas = canvas();

    render(<WorkbenchRail />);
    expect(map()).not.toHaveClass("rail--collapsed");

    fireEvent.keyDown(window, { key: "b", ctrlKey: true });

    expect(map()).toHaveClass("rail--collapsed");
    expect(window.localStorage.getItem("studio.sidebar")).toBe("collapsed");

    fireEvent.keyDown(window, { key: "b", ctrlKey: true });

    expect(map()).not.toHaveClass("rail--collapsed");
    expect(window.localStorage.getItem("studio.sidebar")).toBe("expanded");
  });

  it("starts collapsed when the last person left it collapsed", () => {
    window.localStorage.setItem("studio.sidebar", "collapsed");

    render(<WorkbenchRail />);

    expect(map()).toHaveClass("rail--collapsed");
  });

  it("resolves a stored value this build does not know to expanded", () => {
    window.localStorage.setItem("studio.sidebar", "sideways");

    render(<WorkbenchRail />);

    expect(map()).not.toHaveClass("rail--collapsed");
  });

  it("collapses by default where there is no room for labels", () => {
    matchWidths(1279);
    studio.canvas = canvas();

    render(<WorkbenchRail />);

    expect(map()).toHaveClass("rail--collapsed");
    expect(window.localStorage.getItem("studio.sidebar")).toBeNull();
  });

  it("keeps the label of a collapsed row for a screen reader", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }, { id: "O-2" }] });

    render(<WorkbenchRail />);
    fireEvent.keyDown(window, { key: "b", metaKey: true });

    const row = screen.getByRole("button", { name: "Landscape, 2 opportunities" });
    expect(row).toHaveAttribute("title", "Landscape, 2 opportunities");
  });

  it("leaves Cmd/Ctrl+B to a field that has text selected", () => {
    studio.canvas = canvas();

    render(
      <>
        <textarea data-testid="note" />
        <WorkbenchRail />
      </>,
    );

    const note = screen.getByTestId<HTMLTextAreaElement>("note");
    note.value = "a selected word";
    note.setSelectionRange(2, 10);

    fireEvent.keyDown(note, { key: "b", ctrlKey: true });

    expect(map()).not.toHaveClass("rail--collapsed");
  });

  it("is one tab stop and moves inside it with the arrows", () => {
    studio.canvas = canvas();

    render(<WorkbenchRail />);
    const rows = Array.from(map().querySelectorAll<HTMLButtonElement>(".rail__row"));

    expect(rows.filter((row) => row.tabIndex === 0)).toHaveLength(1);

    rows[1].focus();
    fireEvent.keyDown(rows[1], { key: "ArrowDown" });
    expect(document.activeElement).toBe(rows[2]);

    fireEvent.keyDown(rows[2], { key: "ArrowUp" });
    expect(document.activeElement).toBe(rows[1]);

    fireEvent.keyDown(rows[1], { key: "End" });
    expect(document.activeElement).toBe(rows[rows.length - 1]);

    fireEvent.keyDown(rows[rows.length - 1], { key: "Home" });
    expect(document.activeElement).toBe(rows[0]);
  });

  it("marks the row a signal pointed at, not the first one", () => {
    studio.canvas = canvas();
    studio.activePanel = "evidence";

    render(<WorkbenchRail />);
    const rows = Array.from(map().querySelectorAll<HTMLButtonElement>(".rail__row"));

    expect(rows.filter((row) => row.tabIndex === 0)).toHaveLength(1);
    expect(rows.find((row) => row.tabIndex === 0)?.dataset.panel).toBe("evidence");
  });
});

describe("WorkbenchRail on a narrow screen", () => {
  beforeEach(() => {
    window.localStorage.clear();
    studio.activePanel = null;
    studio.openPanel.mockClear();
    studio.closePanel.mockClear();
  });

  afterEach(() => {
    restoreMatchMedia();
  });

  it("offers the map as a button and opens it as a drawer", () => {
    matchWidths(1023);
    studio.canvas = canvas();

    render(<WorkbenchRail />);

    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Studio map" }));

    const drawer = screen.getByRole("dialog", { name: "Studio" });
    expect(drawer).toHaveAttribute("aria-modal", "true");
    expect(drawer).toContainElement(screen.getByRole("button", { name: "Settings" }));
  });

  it("puts focus inside the drawer", () => {
    matchWidths(1023);
    studio.canvas = canvas();

    render(<WorkbenchRail />);
    fireEvent.click(screen.getByRole("button", { name: "Studio map" }));

    const drawer = screen.getByRole("dialog", { name: "Studio" });
    expect(drawer.contains(document.activeElement)).toBe(true);
  });

  it("closes on Escape and keeps the thread behind it reachable", () => {
    matchWidths(1023);
    studio.canvas = canvas();

    render(<WorkbenchRail />);
    fireEvent.click(screen.getByRole("button", { name: "Studio map" }));

    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(studio.closePanel).not.toHaveBeenCalled();
  });

  it("closes on the scrim", () => {
    matchWidths(1023);
    studio.canvas = canvas();

    render(<WorkbenchRail />);
    fireEvent.click(screen.getByRole("button", { name: "Studio map" }));
    fireEvent.click(screen.getByRole("button", { name: "Close the map" }));

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("closes when a destination is chosen, and opens it", () => {
    matchWidths(1023);
    studio.canvas = canvas();

    render(<WorkbenchRail />);
    fireEvent.click(screen.getByRole("button", { name: "Studio map" }));
    fireEvent.click(screen.getByRole("button", { name: "Schedule, 0 scheduled runs" }));

    expect(studio.openPanel).toHaveBeenCalledWith("schedule");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("never remembers the drawer, only the collapse", () => {
    matchWidths(1023);
    studio.canvas = canvas();

    render(<WorkbenchRail />);
    fireEvent.click(screen.getByRole("button", { name: "Studio map" }));
    fireEvent.keyDown(window, { key: "Escape" });

    expect(window.localStorage.getItem("studio.sidebar")).toBeNull();
  });

  it("has no collapse to toggle while it is a drawer", () => {
    matchWidths(1023);
    studio.canvas = canvas();

    render(<WorkbenchRail />);
    fireEvent.keyDown(window, { key: "b", ctrlKey: true });

    expect(window.localStorage.getItem("studio.sidebar")).toBeNull();
    expect(screen.queryByRole("button", { name: /the map$/i })).toBeNull();
  });
});
