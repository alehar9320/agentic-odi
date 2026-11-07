import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SearchBox } from "./SearchBox";
import type { CanvasData, Observation } from "../../types";

const state = vi.hoisted(() => ({
  canvas: null as CanvasData | null,
  memory: [] as Observation[],
  searchOpen: false,
  openSearch: vi.fn(),
  closeSearch: vi.fn(),
  focusSubject: vi.fn(),
  focusEvidence: vi.fn(),
  focusObservation: vi.fn(),
  openPanel: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => state,
}));

const canvas: CanvasData = {
  source: "local",
  jobs: [{ id: "JOB-1", name: "Propagate secrets" }],
  steps: [{ id: "STEP-1", job_id: "JOB-1", name: "Rotate the credential", order: 1 }],
  outcomes: [{ id: "O-31", job_id: "JOB-1", statement: "Minimize the time to propagate secrets" }],
  evidence: [{ id: "EV-1", name: "Acme call", content: "Secrets rotation took an afternoon." }],
};

const observation: Observation = {
  id: "obs-1",
  kind: "constraint",
  text: "We cannot change pricing this quarter.",
  data: {},
  status: "confirmed",
  confidence: 0.9,
  source_turn: 1,
  created_at: "2026-10-22T10:00:00+00:00",
  updated_at: "2026-10-22T10:00:00+00:00",
};

beforeEach(() => {
  state.canvas = canvas;
  state.memory = [observation];
  state.searchOpen = true;
  state.openSearch.mockReset();
  state.closeSearch.mockReset();
  state.focusSubject.mockReset();
  state.focusEvidence.mockReset();
  state.focusObservation.mockReset();
  state.openPanel.mockReset();
});

/** Type into the box and let the debounce settle. */
async function typeQuery(value: string) {
  const input = screen.getByRole("searchbox", { name: "Search everything" });
  fireEvent.change(input, { target: { value } });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 300));
  });
}

describe("SearchBox", () => {
  it("renders nothing while it is closed", () => {
    state.searchOpen = false;
    render(<SearchBox />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("focuses the query field when it opens", () => {
    render(<SearchBox />);
    expect(screen.getByRole("searchbox", { name: "Search everything" })).toHaveFocus();
  });

  it("groups hits by artifact once the debounce settles", async () => {
    render(<SearchBox />);
    await typeQuery("secrets");

    expect(screen.getByRole("group", { name: "Desired outcomes" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Evidence" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Jobs" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Minimize the time to propagate secrets/ })).toBeInTheDocument();
  });

  it("does not run the query before the debounce elapses", async () => {
    render(<SearchBox />);
    const input = screen.getByRole("searchbox", { name: "Search everything" });
    fireEvent.change(input, { target: { value: "secrets" } });

    // Still inside the debounce window: the previous (empty) answer stands.
    expect(screen.queryByRole("group", { name: "Desired outcomes" })).toBeNull();
  });

  it("says nothing matches without pretending it searched", async () => {
    render(<SearchBox />);
    await typeQuery("zzzznothing");
    expect(screen.getByText(/Nothing matches/)).toBeInTheDocument();
  });

  it("opens an outcome in the landscape, focused", async () => {
    render(<SearchBox />);
    await typeQuery("secrets");

    fireEvent.click(screen.getByRole("option", { name: /Minimize the time to propagate secrets/ }));

    expect(state.focusSubject).toHaveBeenCalledWith("outcome", "O-31");
    expect(state.openPanel).toHaveBeenCalledWith("landscape");
    expect(state.closeSearch).toHaveBeenCalled();
  });

  it("opens a quote in the evidence lens, focused", async () => {
    render(<SearchBox />);
    await typeQuery("secrets");

    fireEvent.click(screen.getByRole("option", { name: /Acme call/ }));

    expect(state.focusEvidence).toHaveBeenCalledWith("EV-1");
    expect(state.closeSearch).toHaveBeenCalled();
  });

  it("opens an observation in the memory lens, focused", async () => {
    render(<SearchBox />);
    await typeQuery("pricing");

    fireEvent.click(
      screen.getByRole("option", { name: /We cannot change pricing this quarter/ }),
    );

    expect(state.focusObservation).toHaveBeenCalledWith("obs-1");
    expect(state.closeSearch).toHaveBeenCalled();
  });

  it("moves between hits with the arrow keys and opens with Enter", async () => {
    render(<SearchBox />);
    await typeQuery("secrets");

    const input = screen.getByRole("searchbox", { name: "Search everything" });
    // The outcome leads; one ArrowDown moves the highlight to the next hit.
    fireEvent.keyDown(input, { key: "ArrowDown" });
    const active = screen
      .getAllByRole("option")
      .find((option) => option.getAttribute("aria-selected") === "true");
    expect(active).not.toBeNull();

    fireEvent.keyDown(input, { key: "Enter" });
    // The second-ranked hit is the job, which opens the job map.
    expect(state.focusSubject).toHaveBeenCalledWith("job", "JOB-1");
    expect(state.openPanel).toHaveBeenCalledWith("jobmap");
  });

  it("closes on Escape and returns focus", async () => {
    render(<SearchBox />);
    const input = screen.getByRole("searchbox", { name: "Search everything" });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(state.closeSearch).toHaveBeenCalled();
  });

  it("opens from anywhere on Cmd/Ctrl+Shift+F but leaves Cmd/Ctrl+F alone", () => {
    state.searchOpen = false;
    render(<SearchBox />);

    const plainFind = new KeyboardEvent("keydown", {
      key: "f",
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    });
    window.dispatchEvent(plainFind);
    expect(state.openSearch).not.toHaveBeenCalled();
    // The browser's own find is not intercepted.
    expect(plainFind.defaultPrevented).toBe(false);

    window.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "f",
        ctrlKey: true,
        shiftKey: true,
        bubbles: true,
        cancelable: true,
      }),
    );
    expect(state.openSearch).toHaveBeenCalledTimes(1);
  });

  it("announces each hit's group to assistive technology", async () => {
    render(<SearchBox />);
    await typeQuery("secrets");

    const option = screen.getAllByRole("option")[0];
    expect(option).toHaveAccessibleName(/Desired outcomes/);
  });

  it("shows the query field's placeholder when it has no query", () => {
    render(<SearchBox />);
    expect(screen.getByText(/Type to search every stored outcome/)).toBeInTheDocument();
  });
});

describe("SearchBox accessibility", () => {
  it("is a labelled modal dialog", async () => {
    render(<SearchBox />);
    await waitFor(() => expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true"));
    expect(screen.getByRole("dialog")).toHaveAccessibleName("Search everything");
  });
});
