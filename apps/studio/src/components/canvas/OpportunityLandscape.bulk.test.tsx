/**
 * ALH-197 (M2-03.2) — the board selects, previews, applies and undoes a bulk run.
 *
 * Every number and sentence here came from the service: the board renders the report
 * it was handed and never derives a change table of its own. The assertions therefore
 * aim at who is asked for what — the checked ids, the named widening, the token — and
 * at what a failure must leave standing.
 */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  BulkReport,
  CanvasData,
  CanvasState,
  Outcome,
  OutcomeSearch,
} from "../../types";
import { OpportunityLandscape } from "./OpportunityLandscape";

const LIBRARY: Outcome[] = [
  { id: "O-1", statement: "Minimize the time it takes to find a payment when reconciling" },
  { id: "O-2", statement: "Minimize the number of exceptions to read before close" },
  { id: "O-3", statement: "Maximize the accuracy of the cash position at close" },
];

const harness = vi.hoisted(() => ({
  search: vi.fn(),
  themes: vi.fn(),
  preview: vi.fn(),
  apply: vi.fn(),
  undo: vi.fn(),
  state: {
    canvasState: { kind: "ready", data: null } as unknown as CanvasState,
    canvasCached: false,
    settings: { mcp_url: "http://mcp" },
    refreshCanvas: vi.fn(),
    openPanel: vi.fn(),
    theses: [] as unknown[],
    deleteThesis: vi.fn(),
    focusedSubject: null as { kind: string; id: string } | null,
    focusSubject: vi.fn(),
    ask: vi.fn(),
    deleteOutcome: vi.fn(),
    pushToast: vi.fn(),
    saveThesis: vi.fn(),
    updateOutcome: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({ useStudio: () => harness.state }));

vi.mock("../../api/studioApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/studioApi")>()),
  fetchOutcomeSearch: harness.search,
  fetchThemes: harness.themes,
  previewBulkOutcomes: harness.preview,
  applyBulkOutcomes: harness.apply,
  undoBulkOutcomes: harness.undo,
}));

function canvas(outcomes = LIBRARY): CanvasData {
  return {
    jobs: [{ id: "JOB-1", name: "Reconcile supplier invoices" }],
    steps: [
      { id: "s-locate", job_id: "JOB-1", name: "Locate the invoice" },
      { id: "s-execute", job_id: "JOB-1", name: "Post the payment" },
    ],
    outcomes,
    evidence: [],
    source: "mcp",
  } as CanvasData;
}

function answer(items: Outcome[], total = items.length): OutcomeSearch {
  return { items, total, facets: { stage: {}, theme: {}, confidence: {} } };
}

const PREVIEW: BulkReport = {
  requested: 2,
  changed: ["O-1", "O-2"],
  skipped: [{ id: "O-3", reason: "the theme organizes a different job" }],
  changes: [
    { outcome_id: "O-1", field: "theme_ids", from: [], to: ["t-1"] },
    { outcome_id: "O-2", field: "step_id", from: "s-locate", to: "s-execute" },
  ],
  undo_token: null,
};

const APPLIED: BulkReport = {
  ...PREVIEW,
  undo_token: "b-7",
};

const UNDONE: BulkReport = {
  requested: 2,
  changed: ["O-1", "O-2"],
  skipped: [],
  changes: [
    { outcome_id: "O-1", field: "theme_ids", from: ["t-1"], to: [] },
    { outcome_id: "O-2", field: "step_id", from: "s-execute", to: "s-locate" },
  ],
  undo_token: null,
};

function check(id: string) {
  fireEvent.click(screen.getByRole("checkbox", { name: new RegExp(`select ${id}`, "i") }));
}

function toCards() {
  fireEvent.click(screen.getByRole("button", { name: /visual cards/i }));
}

function searchFor(text: string, total: number) {
  harness.search.mockResolvedValue(answer(LIBRARY, total));
  fireEvent.change(screen.getByRole("textbox", { name: /search outcomes/i }), {
    target: { value: text },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
}

function bar(): HTMLElement {
  return screen.getByRole("region", { name: /bulk change/i });
}

function dialog(): HTMLElement {
  return screen.getByRole("dialog");
}

function draftChange(themeId = "t-1") {
  fireEvent.change(within(bar()).getByRole("combobox", { name: /theme to add/i }), {
    target: { value: themeId },
  });
}

beforeEach(() => {
  harness.search.mockReset();
  harness.search.mockResolvedValue(answer(LIBRARY, 3));
  harness.themes.mockReset();
  harness.themes.mockResolvedValue([
    { id: "t-1", name: "Cash timing", ordinal: 0 },
    { id: "t-2", name: "Exception handling", ordinal: 1 },
  ]);
  harness.preview.mockReset();
  harness.preview.mockResolvedValue(PREVIEW);
  harness.apply.mockReset();
  harness.apply.mockResolvedValue(APPLIED);
  harness.undo.mockReset();
  harness.undo.mockResolvedValue(UNDONE);
  harness.state.canvasState = { kind: "ready", data: canvas() } as unknown as CanvasState;
  harness.state.focusedSubject = null;
  harness.state.refreshCanvas.mockReset();
  harness.state.focusSubject.mockClear();
});

describe("the selection", () => {
  it("is the checked rows, and does not move the detail panel", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));
    toCards();

    check("O-1");
    check("O-2");

    expect(within(bar()).getByText(/^2 selected$/i)).toBeInTheDocument();
    // Ticking ten rows is one interaction per row, not an opening of the panel.
    expect(harness.state.focusSubject).not.toHaveBeenCalled();
  });

  it("offers the wider run by name and count when a filter is on", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));
    toCards();

    searchFor("payment", 137);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));
    check("O-1");

    expect(within(bar()).getByRole("button", { name: /preview all 137 matching/i })).toBeInTheDocument();
    expect(within(bar()).getByRole("button", { name: /preview 1 selected/i })).toBeInTheDocument();
    expect(within(bar()).getByText(/^1 selected$/i)).toBeInTheDocument();
  });

  it("is absent, and asks for nothing, while nothing is checked", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));
    toCards();

    expect(screen.queryByRole("region", { name: /bulk change/i })).not.toBeInTheDocument();
    expect(harness.preview).not.toHaveBeenCalled();
  });

  it("clears on request", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));
    toCards();

    check("O-1");
    fireEvent.click(within(bar()).getByRole("button", { name: /clear selection/i }));

    expect(screen.queryByRole("region", { name: /bulk change/i })).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /select O-1/i })).not.toBeChecked();
  });
});

describe("the preview", () => {
  it("names the checked ids and the drafted change, and writes nothing", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));
    toCards();

    check("O-1");
    check("O-2");
    draftChange();
    fireEvent.click(within(bar()).getByRole("button", { name: /preview 2 selected/i }));

    await waitFor(() => expect(harness.preview).toHaveBeenCalledTimes(1));
    expect(harness.preview.mock.calls[0]?.[0]).toMatchObject({
      mcpUrl: "http://mcp",
      outcomeIds: ["O-1", "O-2"],
      addThemeIds: ["t-1"],
    });
    expect(harness.apply).not.toHaveBeenCalled();

    // One table row per change, with the before and the after it reported.
    const rows = within(dialog()).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    expect(within(rows[0]!).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "O-1",
      "Themes",
      "—",
      "Cash timing",
    ]);
    expect(within(rows[1]!).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "O-2",
      "Job step",
      "Locate the invoice",
      "Post the payment",
    ]);
  });

  it("lists a skipped row with the service's reason", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));
    toCards();

    check("O-1");
    draftChange();
    fireEvent.click(within(bar()).getByRole("button", { name: /preview 1 selected/i }));

    const box = await screen.findByRole("dialog");
    const skipped = await within(box).findByRole("list", { name: /skipped/i });
    expect(skipped.textContent).toContain("O-3");
    expect(skipped.textContent).toContain("the theme organizes a different job");
  });

  it("refuses to widen without a named count and sends the narrowing instead", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));
    toCards();

    searchFor("payment", 137);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));
    check("O-1");
    draftChange();
    fireEvent.click(within(bar()).getByRole("button", { name: /preview all 137 matching/i }));

    await waitFor(() => expect(harness.preview).toHaveBeenCalledTimes(1));
    expect(harness.preview.mock.calls[0]?.[0]).toMatchObject({
      outcomeIds: ["O-1"],
      query: { text: "payment" },
    });
  });
});

describe("applying and taking back", () => {
  async function previewed() {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));
    toCards();
    check("O-1");
    check("O-2");
    draftChange();
    fireEvent.click(within(bar()).getByRole("button", { name: /preview 2 selected/i }));
    await waitFor(() => expect(harness.preview).toHaveBeenCalledTimes(1));
  }

  it("writes the set the preview counted and counts what it skipped", async () => {
    await previewed();

    fireEvent.click(within(dialog()).getByRole("button", { name: /^apply/i }));

    await waitFor(() => expect(harness.apply).toHaveBeenCalledTimes(1));
    expect(harness.apply.mock.calls[0]?.[0]).toMatchObject({ outcomeIds: ["O-1", "O-2"] });

    // The partial run says so: two changed, one skipped, never "all done".
    expect(within(dialog()).getByText(/2 changed/i)).toBeInTheDocument();
    expect(dialog().textContent).toContain("1 skipped");
  });

  it("undoes with the token the write returned and closes on what came back", async () => {
    await previewed();
    fireEvent.click(within(dialog()).getByRole("button", { name: /^apply/i }));
    await waitFor(() => expect(harness.apply).toHaveBeenCalledTimes(1));

    fireEvent.click(within(dialog()).getByRole("button", { name: /^undo/i }));

    await waitFor(() => expect(harness.undo).toHaveBeenCalledWith("http://mcp", "b-7"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(harness.state.refreshCanvas).toHaveBeenCalled();
  });

  it("shows an expired token's own sentence and leaves the rows as the store wrote them", async () => {
    await previewed();
    fireEvent.click(within(dialog()).getByRole("button", { name: /^apply/i }));
    await waitFor(() => expect(harness.apply).toHaveBeenCalledTimes(1));

    harness.undo.mockRejectedValue(
      Object.assign(new Error("That undo token was taken by a newer run."), { name: "StudioApiError" }),
    );
    const refreshed = harness.state.refreshCanvas.mock.calls.length;
    fireEvent.click(within(dialog()).getByRole("button", { name: /^undo/i }));

    expect(
      await within(dialog()).findByText("That undo token was taken by a newer run."),
    ).toBeInTheDocument();
    // No optimistic restore: the board asks the store what it holds and shows that.
    await waitFor(() => expect(harness.state.refreshCanvas).toHaveBeenCalledTimes(refreshed + 1));
    expect(within(dialog()).queryByRole("button", { name: /^apply/i })).not.toBeInTheDocument();
  });
});

describe("a refused run keeps its context", () => {
  it("keeps the selection and the drafted change, and shows the sentence the service wrote", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));
    toCards();

    check("O-1");
    draftChange();
    harness.preview.mockRejectedValue(
      Object.assign(new Error("Nothing to change: name a theme, a stage, or a tag."), {
        name: "StudioApiError",
      }),
    );
    fireEvent.click(within(bar()).getByRole("button", { name: /preview 1 selected/i }));

    expect(
      await screen.findByText("Nothing to change: name a theme, a stage, or a tag."),
    ).toBeInTheDocument();

    // Still there, still drafted, so the person can fix it and press the same button.
    expect(within(bar()).getByText(/^1 selected$/i)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /select O-1/i })).toBeChecked();
    expect(
      within(bar()).getByRole("combobox", { name: /theme to add/i }),
    ).toHaveValue("t-1");

    harness.preview.mockResolvedValue(PREVIEW);
    fireEvent.click(within(bar()).getByRole("button", { name: /preview 1 selected/i }));
    await waitFor(() => expect(harness.preview).toHaveBeenCalledTimes(2));
    expect(harness.preview.mock.calls[1]?.[0]).toMatchObject({ addThemeIds: ["t-1"] });
  });
});
