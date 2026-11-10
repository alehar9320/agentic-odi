import { act, render } from "@testing-library/react";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { beforeEach, describe, expect, it } from "vitest";

import { CountedSurface, RenderCounter, expectRenderBudget, getCounts, resetCounts } from "./renderCounts";

describe("RenderCounter", () => {
  beforeEach(() => {
    resetCounts();
  });

  it("counts each render of the component it names", () => {
    const { rerender } = render(<RenderCounter id="composer" />);
    rerender(<RenderCounter id="composer" />);

    expect(getCounts().composer).toBe(2);
  });

  it("keeps one total per name", () => {
    render(
      <>
        <RenderCounter id="composer" />
        <RenderCounter id="landscape" />
        <RenderCounter id="landscape" />
      </>,
    );

    expect(getCounts()).toEqual({ composer: 1, landscape: 2 });
  });

  it("starts over when the counts are reset", () => {
    render(<RenderCounter id="rail" />);
    resetCounts();

    expect(getCounts()).toEqual({});
  });
});

/**
 * The case the budget depends on: a surface that re-renders because it reads
 * context, inside a tree that does not re-render with it. A counter placed
 * beside the surface sees nothing here — only a count of the subtree does — so
 * this is the behavior the harness has to get right.
 */
const Reading = createContext({ value: 0 });

function Holder({
  children,
  onReady,
}: {
  children: ReactNode;
  onReady: (readAgain: () => void) => void;
}) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    onReady(() => setValue((current) => current + 1));
  }, [onReady]);
  // A new object each time, so the consumer really does re-render.
  return <Reading.Provider value={useMemo(() => ({ value }), [value])}>{children}</Reading.Provider>;
}

function Reader() {
  const { value } = useContext(Reading);
  return <span>{value}</span>;
}

describe("CountedSurface", () => {
  beforeEach(() => {
    resetCounts();
  });

  it("counts the renders of the subtree it wraps", () => {
    let readAgain: () => void = () => {};
    render(
      <Holder onReady={(again) => { readAgain = again; }}>
        <RenderCounter id="beside" />
        <CountedSurface id="landscape">
          <Reader />
        </CountedSurface>
      </Holder>,
    );

    expect(getCounts()).toEqual({ beside: 1, landscape: 1 });

    act(() => readAgain());

    expect(getCounts()).toEqual({ beside: 1, landscape: 2 });
  });

  it("counts a surface that re-renders on its own without a context consumer", () => {
    const { rerender } = render(
      <Holder onReady={() => {}}>
        <CountedSurface id="rail">
          <Reader />
        </CountedSurface>
      </Holder>,
    );

    rerender(
      <Holder onReady={() => {}}>
        <CountedSurface id="rail">
          <Reader />
        </CountedSurface>
      </Holder>,
    );

    expect(getCounts().rail).toBe(2);
  });
});

/**
 * The ratchet is only useful if a rise points at the surface that caused it:
 * the numbers are per surface, and an aggregate would let one surface's
 * regression hide behind another's improvement.
 */
describe("expectRenderBudget", () => {
  beforeEach(() => {
    resetCounts();
  });

  it("says nothing while every named surface stays at its number", () => {
    render(<RenderCounter id="composer" />);

    expect(() => expectRenderBudget({ composer: 1, landscape: 0 })).not.toThrow();
  });

  it("names the surface that went over its number", () => {
    render(<RenderCounter id="composer" />);
    render(<RenderCounter id="composer" />);

    expect(() => expectRenderBudget({ composer: 1, landscape: 0 })).toThrow(/composer renders 2, budget is 1/);
  });

  it("names a counted surface that the budget forgot to bound", () => {
    render(<RenderCounter id="rail" />);

    expect(() => expectRenderBudget({ composer: 0 })).toThrow(/rail/);
  });
});
