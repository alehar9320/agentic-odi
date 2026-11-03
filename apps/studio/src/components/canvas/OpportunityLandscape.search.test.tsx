/**
 * ALH-195 (M2-02.2) — the landscape narrows by asking, not by filtering.
 *
 * Every assertion here is about who does the work: the sidecar answers with
 * items, a total, and per-dimension counts, and the landscape renders those
 * numbers rather than deriving its own. The ticket's five acceptance cases are
 * the five describes below.
 */

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CanvasData, CanvasState, Outcome, OutcomeFacets, OutcomeSearch } from "../../types";
import { OpportunityLandscape } from "./OpportunityLandscape";

const LIBRARY: Outcome[] = [
  {
    id: "O-1",
    statement: "Minimize the time it takes to find a payment when reconciling",
    importance: 8,
    satisfaction: 2,
    opportunity_score: 14,
  },
  {
    id: "O-2",
    statement: "Minimize the number of exceptions to read before close when reconciling",
    importance: 6,
    satisfaction: 4,
    opportunity_score: 8,
  },
  {
    id: "O-3",
    statement: "Maximize the accuracy of the cash position at close",
    importance: 5,
    satisfaction: 5,
    opportunity_score: 5,
  },
];

const harness = vi.hoisted(() => ({
  search: vi.fn(),
  themes: vi.fn(),
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
  },
}));

vi.mock("../../state/StudioContext", () => ({ useStudio: () => harness.state }));

vi.mock("../../api/studioApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/studioApi")>()),
  fetchOutcomeSearch: harness.search,
  fetchThemes: harness.themes,
}));

const STAGES = ["define", "locate", "prepare", "confirm", "execute", "monitor", "modify", "conclude"];

function zeroStages(except: Record<string, number> = {}): Record<string, number> {
  return Object.fromEntries(STAGES.map((stage) => [stage, except[stage] ?? 0]));
}

function facets(over: Partial<OutcomeFacets> = {}): OutcomeFacets {
  return { stage: zeroStages(), theme: {}, confidence: { scored: 0, unscored: 0 }, ...over };
}

function answer(items: Outcome[], total = items.length, facetCounts = facets()): OutcomeSearch {
  return { items, total, facets: facetCounts };
}

const WHOLE_LIBRARY = answer(
  LIBRARY,
  3,
  facets({
    stage: zeroStages({ execute: 3 }),
    confidence: { scored: 2, unscored: 1 },
    theme: { "t-1": 2, "t-2": 1 },
  }),
);

function canvas(outcomes = LIBRARY, source: CanvasData["source"] = "mcp"): CanvasData {
  return {
    jobs: [{ id: "JOB-1", name: "Reconcile supplier invoices" }],
    steps: [],
    outcomes,
    evidence: [],
    source,
  } as CanvasData;
}

function deferred() {
  let resolve!: (value: OutcomeSearch) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<OutcomeSearch>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function searchField(): HTMLElement {
  return screen.getByRole("textbox", { name: /search outcomes/i });
}

function submitNarrowing() {
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
}

/** The ids in the rendered table, top to bottom. */
function renderedRows(): string[] {
  fireEvent.click(screen.getByRole("button", { name: /table view/i }));
  return screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[0]?.textContent ?? "");
}

function filtersOf(index: number): Record<string, unknown> {
  return harness.search.mock.calls[index]?.[1] as Record<string, unknown>;
}

beforeEach(() => {
  harness.search.mockReset();
  harness.search.mockResolvedValue(WHOLE_LIBRARY);
  harness.themes.mockReset();
  harness.themes.mockResolvedValue([
    { id: "t-1", name: "Cash timing", ordinal: 0 },
    { id: "t-2", name: "Exception handling", ordinal: 1 },
  ]);
  harness.state.canvasState = { kind: "ready", data: canvas() } as unknown as CanvasState;
  harness.state.focusedSubject = null;
  harness.state.focusSubject.mockClear();
});

describe("asking the store rather than filtering the loaded list", () => {
  it("opens on an unfiltered page of the library", async () => {
    render(<OpportunityLandscape />);

    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    expect(harness.search).toHaveBeenCalledWith("http://mcp", { limit: 50, offset: 0 });
  });

  it("sends the text and two facets as one equivalent query", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    fireEvent.change(searchField(), { target: { value: "payment" } });
    submitNarrowing();
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole("button", { name: /^execute/i }));
    fireEvent.click(screen.getByRole("button", { name: /^unscored/i }));

    // One request carries all three dimensions, so the server narrows once and
    // the browser never intersects two answers itself.
    await waitFor(() => {
      expect(filtersOf(harness.search.mock.calls.length - 1)).toEqual({
        text: "payment",
        stage: "execute",
        confidence: "unscored",
        limit: 50,
        offset: 0,
      });
    });
  });

  it("renders the items and the counts the sidecar returned, not its own", async () => {
    harness.search.mockResolvedValue(
      answer([LIBRARY[1]], 1, facets({ stage: zeroStages({ execute: 7 }), theme: { "t-1": 7 }, confidence: { scored: 1, unscored: 0 } })),
    );

    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    fireEvent.change(searchField(), { target: { value: "exceptions" } });
    submitNarrowing();
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));

    // Seven is a number this browser could not have derived from three rows.
    expect(screen.getByRole("button", { name: /^execute.*7/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cash timing.*7/i })).toBeInTheDocument();
    expect(screen.getByText("1 outcome matches these filters")).toBeInTheDocument();

    expect(renderedRows()).toEqual(["O-2"]);
  });

  it("sends the score band and a theme as filters beside the text", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByRole("spinbutton", { name: /minimum score/i }), {
      target: { value: "8" },
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: /maximum score/i }), {
      target: { value: "12" },
    });
    submitNarrowing();
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole("button", { name: /cash timing/i }));

    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(3));

    expect(filtersOf(1)).toMatchObject({ minScore: 8, maxScore: 12 });
    expect(filtersOf(2)).toMatchObject({ minScore: 8, maxScore: 12, themeIds: ["t-1"] });
  });
});

describe("nothing matches", () => {
  it("says nothing matches and offers to clear rather than showing the library", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    harness.search.mockResolvedValue(answer([], 0, facets()));
    fireEvent.change(searchField(), { target: { value: "elephants" } });
    submitNarrowing();

    expect(await screen.findByText(/nothing matches these filters/i)).toBeInTheDocument();
    expect(screen.queryByText(/Minimize the time it takes to find a payment/i)).not.toBeInTheDocument();

    harness.search.mockResolvedValue(WHOLE_LIBRARY);
    fireEvent.click(screen.getByRole("button", { name: /clear filters/i }));

    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(3));
    expect(filtersOf(2)).toEqual({ limit: 50, offset: 0 });
    expect(await screen.findByText(/all 3 outcomes in the library/i)).toBeInTheDocument();
  });

  it("removing the one active chip returns the unfiltered query", async () => {
    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: /^execute/i }));
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));

    fireEvent.click(await screen.findByRole("button", { name: /remove stage filter/i }));

    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(3));
    expect(filtersOf(2)).toEqual({ limit: 50, offset: 0 });
  });
});

describe("loading, failure, and zero matches are three different answers", () => {
  it("shows a searching state that is neither a failure nor zero matches", async () => {
    const pending = deferred();
    harness.search.mockReturnValue(pending.promise);

    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    fireEvent.change(searchField(), { target: { value: "payment" } });
    submitNarrowing();

    expect(await screen.findByRole("status", { name: /searching the library/i })).toBeInTheDocument();
    expect(screen.queryByText(/nothing matches these filters/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("row")).not.toBeInTheDocument();

    await act(async () => {
      pending.resolve(answer([LIBRARY[0]], 1));
    });

    expect(renderedRows()).toEqual(["O-1"]);
  });

  it("shows the failure with a retry, and does not call it zero matches", async () => {
    harness.search.mockRejectedValue(new Error("The studio sidecar isn't reachable."));

    render(<OpportunityLandscape />);

    expect(await screen.findByText("The studio sidecar isn't reachable.")).toBeInTheDocument();
    expect(screen.queryByText(/nothing matches these filters/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));
  });
});

describe("a late answer cannot overtake the current query", () => {
  it("keeps the newest query's rows when an older answer arrives after it", async () => {
    const first = deferred();
    const second = deferred();
    harness.search
      .mockResolvedValueOnce(WHOLE_LIBRARY)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    fireEvent.change(searchField(), { target: { value: "payment" } });
    submitNarrowing();
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole("button", { name: /^execute/i }));
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(3));

    await act(async () => {
      second.resolve(answer([LIBRARY[2]], 1));
    });
    expect(screen.getByText("Maximize the accuracy of the cash position at close")).toBeInTheDocument();

    await act(async () => {
      first.resolve(answer([LIBRARY[0], LIBRARY[1]], 2));
    });

    expect(screen.queryByText(/Minimize the time it takes to find a payment/i)).not.toBeInTheDocument();
    expect(screen.getByText("Maximize the accuracy of the cash position at close")).toBeInTheDocument();
  });
});

describe("paging", () => {
  const pageOne = answer(LIBRARY, 120, facets({ stage: zeroStages({ execute: 120 }) }));
  const pageTwo = answer(
    [{ ...LIBRARY[2], id: "O-9", statement: "Minimize the effort of a re-send when reconciling" }, LIBRARY[0]],
    120,
    facets({ stage: zeroStages({ execute: 120 }) }),
  );

  it("keeps the active filters and the server's order on the next page", async () => {
    harness.search.mockResolvedValue(pageOne);

    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: /^execute/i }));
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));
    expect(renderedRows()).toEqual(["O-1", "O-2", "O-3"]);

    harness.search.mockResolvedValue(pageTwo);
    fireEvent.click(screen.getByRole("button", { name: /next page/i }));

    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(3));
    expect(filtersOf(2)).toEqual({ stage: "execute", limit: 50, offset: 50 });

    // The server put O-9 first; re-sorting here would be a second ordering.
    expect(renderedRows()).toEqual(["O-9", "O-1"]);
    expect(screen.getByRole("status", { name: /page 2 of 3/i })).toBeInTheDocument();
  });

  it("answers a page change with the searching state, not the page it is leaving", async () => {
    harness.search.mockResolvedValueOnce(pageOne).mockResolvedValueOnce(pageOne);
    const pending = deferred();
    harness.search.mockReturnValue(pending.promise);

    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: /^execute/i }));
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));
    expect(renderedRows()).toEqual(["O-1", "O-2", "O-3"]);

    fireEvent.click(screen.getByRole("button", { name: /next page/i }));

    // Page one's rows answer a different query than the one just asked, so they
    // are not the answer to this one: the board says it is searching.
    expect(await screen.findByRole("status", { name: /searching the library/i })).toBeInTheDocument();

    await act(async () => {
      pending.resolve(pageTwo);
    });
    expect(renderedRows()).toEqual(["O-9", "O-1"]);
  });

  it("returns to the first page with the filters still applied", async () => {
    harness.search.mockResolvedValueOnce(pageOne).mockResolvedValue(pageTwo);

    render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: /^execute/i }));
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole("button", { name: /next page/i }));
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(3));

    fireEvent.click(screen.getByRole("button", { name: /previous page/i }));

    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(4));
    expect(filtersOf(3)).toEqual({ stage: "execute", limit: 50, offset: 0 });
  });
});

describe("the demo board is not a library", () => {
  it("keeps the demo landscape out of the store and says why", async () => {
    harness.state.canvasState = {
      kind: "ready",
      data: canvas(LIBRARY, "seed"),
    } as unknown as CanvasState;

    render(<OpportunityLandscape />);

    expect(searchField()).toBeDisabled();
    expect(screen.getByText(/narrowing asks the store/i)).toBeInTheDocument();
    expect(screen.getByText(/this demo board/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^execute/i })).not.toBeInTheDocument();
    expect(harness.search).not.toHaveBeenCalled();
  });

  it("narrows a canvas the sidecar read straight from its own store", async () => {
    harness.state.canvasState = {
      kind: "ready",
      data: canvas(LIBRARY, "local"),
    } as unknown as CanvasState;

    render(<OpportunityLandscape />);

    // `source: "local"` is how the default sidecar labels a store read that
    // made no MCP round trip; the outcomes are in the store all the same.
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));
    expect(searchField()).toBeEnabled();
  });
});

describe("a refreshed library refreshes the counts", () => {
  it("re-asks when the canvas came back with a new generation", async () => {
    const { rerender } = render(<OpportunityLandscape />);
    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(1));

    act(() => {
      harness.state.canvasState = {
        kind: "ready",
        data: {
          ...canvas(),
          provenance: {
            kind: "live",
            reason: "store",
            generated_at: "2026-11-02T10:00:00+00:00",
            record_counts: { jobs: 1, steps: 0, outcomes: 3, evidence: 0 },
          },
        },
      } as unknown as CanvasState;
    });
    rerender(<OpportunityLandscape />);

    await waitFor(() => expect(harness.search).toHaveBeenCalledTimes(2));

    rerender(<OpportunityLandscape />);
    expect(harness.search).toHaveBeenCalledTimes(2);
  });
});
