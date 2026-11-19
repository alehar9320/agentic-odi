import { act, render, waitFor } from "@testing-library/react";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { beforeEach, describe, expect, it } from "vitest";

import { CountedStudio, CountedSurface, RenderCounter, expectRenderBudget, getCounts, resetCounts } from "./renderCounts";
import { NoticesProvider, useNoticesActions, useToasts } from "../state/notices/NoticesContext";
import { SettingsProvider, useSettings } from "../state/settings/SettingsContext";
import type { StudioContextValue } from "../state/StudioContext";

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

/**
 * The split the context refactor (#503) is paid for by: a toast push must not
 * cost a canvas render, and settings readers must not pay for toasts.
 */
describe("context split (#503)", () => {
  beforeEach(() => {
    resetCounts();
  });

  function PushToastTrigger({
    onCapture,
  }: {
    onCapture: (pushToast: () => number) => void;
  }): ReactNode {
    const { pushToast } = useNoticesActions();
    useEffect(() => {
      onCapture(() => pushToast("info", "The sidecar is back."));
    }, [onCapture, pushToast]);
    return null;
  }

  function SettingsReader(): ReactNode {
    const { settings } = useSettings();
    return <span>{settings.base_url}</span>;
  }

  function ToastsReader(): ReactNode {
    const toasts = useToasts();
    return <span>{String(toasts.length)}</span>;
  }

  function ThemeTrigger({ onCapture }: { onCapture: (setTheme: () => void) => void }): ReactNode {
    const { setTheme } = useSettings();
    useEffect(() => {
      onCapture(() => setTheme("light"));
    }, [onCapture, setTheme]);
    return null;
  }

  it("a toast push does not re-render the composer or landscape", async () => {
    let studio: StudioContextValue | undefined;
    render(
      <CountedStudio
        onStudio={(value) => {
          studio = value;
        }}
      />,
    );
    await waitFor(() => expect(studio).toBeDefined());

    const before = { ...getCounts() };
    await act(async () => {
      void studio!.pushToast("info", "The sidecar is back.");
    });

    expect(getCounts().composer).toBe(before.composer);
    expect(getCounts().landscape).toBe(before.landscape);
  });

  it("an action-only consumer does not re-render on a new toast", () => {
    let pushToast: (() => number) | null = null;
    render(
      <NoticesProvider>
        <PushToastTrigger onCapture={(fn) => { pushToast = fn; }} />
        <CountedSurface id="actions">
          <ActionsReader />
        </CountedSurface>
      </NoticesProvider>,
    );

    const before = getCounts().actions ?? 0;
    act(() => {
      void pushToast!();
    });
    expect(getCounts().actions).toBe(before);
  });

  function ActionsReader(): ReactNode {
    const { pushToast } = useNoticesActions();
    return <span>{String(pushToast.length)}</span>;
  }

  it("a settings reader does not re-render on a toast push", () => {
    let pushToast: (() => number) | null = null;
    render(
      <SettingsProvider>
        <NoticesProvider>
          <PushToastTrigger onCapture={(fn) => { pushToast = fn; }} />
          <CountedSurface id="settings-reader">
            <SettingsReader />
          </CountedSurface>
        </NoticesProvider>
      </SettingsProvider>,
    );

    const before = getCounts()["settings-reader"] ?? 0;
    act(() => {
      void pushToast!();
    });
    expect(getCounts()["settings-reader"]).toBe(before);
  });

  it("a toast consumer does not re-render on a theme change", () => {
    let setTheme: (() => void) | null = null;
    render(
      <SettingsProvider>
        <NoticesProvider>
          <ThemeTrigger onCapture={(fn) => { setTheme = fn; }} />
          <CountedSurface id="toasts-reader">
            <ToastsReader />
          </CountedSurface>
        </NoticesProvider>
      </SettingsProvider>,
    );

    const before = getCounts()["toasts-reader"] ?? 0;
    act(() => {
      void setTheme!();
    });
    expect(getCounts()["toasts-reader"]).toBe(before);
  });
});
