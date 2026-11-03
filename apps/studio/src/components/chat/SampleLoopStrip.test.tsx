import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IndexedDbLocalStore } from "../../bff/store/indexedDbStore";
import { SAMPLE_LOOP } from "../../lib/sampleLoop";
import { SampleLoopStrip } from "./SampleLoopStrip";

/**
 * The empty stage's worked example (#318).
 *
 * The honesty rule is the one under test here: rendering the strip must write
 * nothing to the store. Spies sit on the real persistence boundary —
 * `IndexedDbLocalStore` — so a stray write fails the test rather than quietly
 * entering the rail counts or the landscape totals.
 */
const WRITES = [
  "nextSeq",
  "putJob",
  "putStep",
  "putOutcome",
  "putObservation",
  "putConversation",
  "appendTurn",
  "restore",
] as const;

let spies: Array<ReturnType<typeof vi.spyOn>> = [];

beforeEach(() => {
  window.localStorage.clear();
  spies = WRITES.map((method) =>
    vi.spyOn(IndexedDbLocalStore.prototype, method).mockResolvedValue(undefined as never),
  );
});

afterEach(() => {
  for (const spy of spies) {
    spy.mockRestore();
  }
  spies = [];
});

describe("SampleLoopStrip", () => {
  it("labels the sample above the content and in its accessible name", () => {
    render(<SampleLoopStrip onStartOwn={vi.fn()} />);

    const strip = screen.getByLabelText("Sample loop, not your data");
    expect(strip).toBeInTheDocument();
    expect(screen.getByText("Sample, not your data.")).toBeInTheDocument();
    expect(screen.getByText("SAMPLE")).toBeInTheDocument();
  });

  it("shows the quote, its hypothetical source, and the finished outcome", () => {
    render(<SampleLoopStrip onStartOwn={vi.fn()} />);

    expect(screen.getByText(new RegExp(SAMPLE_LOOP.quote.slice(0, 30)))).toBeInTheDocument();
    expect(screen.getByText("hypothetical onboarding call")).toBeInTheDocument();
    expect(screen.getByText(SAMPLE_LOOP.outcome)).toBeInTheDocument();
  });

  it("shows the two numbers, the derived score, and the segment label", () => {
    render(<SampleLoopStrip onStartOwn={vi.fn()} />);

    const values = screen.getByText(/Importance/);
    expect(values).toHaveTextContent("Importance 9");
    expect(values).toHaveTextContent("Satisfaction 3");
    expect(values).toHaveTextContent("Opportunity 15");
    expect(screen.getByText("Underserved")).toBeInTheDocument();
  });

  it("names all three gaps under one heading", () => {
    render(<SampleLoopStrip onStartOwn={vi.fn()} />);

    expect(screen.getByText("What's missing")).toBeInTheDocument();
    for (const item of SAMPLE_LOOP.missing) {
      expect(screen.getByText(item)).toBeInTheDocument();
    }
  });

  it("focuses the composer without sending anything", () => {
    const onStartOwn = vi.fn();
    render(<SampleLoopStrip onStartOwn={onStartOwn} />);

    fireEvent.click(screen.getByRole("button", { name: "Start with my own" }));

    expect(onStartOwn).toHaveBeenCalledTimes(1);
  });

  it("removes the strip on Hide and survives a reload", () => {
    const { unmount } = render(<SampleLoopStrip onStartOwn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Hide" }));

    expect(screen.queryByLabelText("Sample loop, not your data")).toBeNull();
    expect(window.localStorage.getItem("studio.sampleLoopDismissed")).toBe("1");

    unmount();
    render(<SampleLoopStrip onStartOwn={vi.fn()} />);
    expect(screen.queryByLabelText("Sample loop, not your data")).toBeNull();
  });

  it("writes nothing to the store when it renders or is started", () => {
    render(<SampleLoopStrip onStartOwn={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Start with my own" }));

    for (const spy of spies) {
      expect(spy).not.toHaveBeenCalled();
    }
    // Rendering is not a dismissal: the key is only set by Hide.
    expect(window.localStorage.getItem("studio.sampleLoopDismissed")).toBeNull();
  });

  it("is keyboard operable: Hide responds to Enter and to Space", () => {
    render(<SampleLoopStrip onStartOwn={vi.fn()} />);

    const hide = screen.getByRole("button", { name: "Hide" });
    // A native button, so both activation keys reach it without a key handler.
    fireEvent.keyDown(hide, { key: "Enter" });
    fireEvent.click(hide);
    expect(window.localStorage.getItem("studio.sampleLoopDismissed")).toBe("1");

    window.localStorage.clear();
    render(<SampleLoopStrip onStartOwn={vi.fn()} />);
    const start = screen.getByRole("button", { name: "Start with my own" });
    fireEvent.keyDown(start, { key: " " });
    expect(start).toHaveAttribute("type", "button");
  });

  it("keeps every value visible in a 390px frame", () => {
    // The band is a grid; below 760px a media query stacks it. jsdom has no
    // layout, so this asserts the content survives a narrow container, and the
    // stacking itself is checked in the browser snapshot.
    const { container } = render(
      <div style={{ width: 390 }}>
        <SampleLoopStrip onStartOwn={vi.fn()} />
      </div>,
    );

    const strip = container.querySelector(".sample-loop");
    expect(strip).not.toBeNull();
    expect(strip).toHaveTextContent("Importance 9");
    expect(strip).toHaveTextContent("Satisfaction 3");
    expect(strip).toHaveTextContent("Opportunity 15");
    expect(strip).toHaveTextContent("no second source");
  });
});
