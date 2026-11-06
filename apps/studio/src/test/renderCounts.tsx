/**
 * Render counting for the Studio's performance budgets (#502).
 *
 * The point is a number a reviewer can argue with, not a profile: a surface
 * that renders more often than its recorded baseline fails the test and names
 * itself. Everything here lives under `src/test/` and is imported only by
 * tests, so it never reaches the production bundle.
 */

import { fireEvent } from "@testing-library/react";
import { Profiler, useEffect, type ReactNode } from "react";
import { expect } from "vitest";

import { BannerBridge } from "../banners/BannerBridge";
import { BannerProvider } from "../banners/BannerProvider";
import { BannerStack } from "../banners/BannerStack";
import { StudioRuntimeProvider } from "../assistant/StudioRuntime";
import type { StudioCommand } from "../lib/commands";
import { OpportunityLandscape } from "../components/canvas/OpportunityLandscape";
import { ThreadComposer } from "../components/chat/ThreadComposer";
import { WorkbenchRail } from "../components/workspace/WorkbenchRail";
import { StudioProvider, useStudio, type StudioContextValue } from "../state/StudioContext";

const counts = new Map<string, number>();

function bump(id: string): void {
  counts.set(id, (counts.get(id) ?? 0) + 1);
}

/** Counts every render of the tree it is placed in, under the given name. */
export function RenderCounter({ id }: { id: string }): ReactNode {
  bump(id);
  return null;
}

/**
 * Counts every commit in which the subtree rendered, which a counter placed
 * beside it cannot see: a surface that re-renders because it reads context
 * re-renders alone, and the wrapper above it stays put. That is precisely the
 * number the split issues (#503, #504, #505) are allowed to lower.
 */
export function CountedSurface({ id, children }: { id: string; children: ReactNode }): ReactNode {
  return <Profiler id={id} onRender={() => bump(id)}>{children}</Profiler>;
}

/** Forget every count, so one scenario starts from zero. */
export function resetCounts(): void {
  counts.clear();
}

/** The counts collected so far, by name. */
export function getCounts(): Record<string, number> {
  return Object.fromEntries(counts);
}

/**
 * Assert the collected counts against a recorded baseline, exactly.
 *
 * A surface that renders more than its number fails with its own name in the
 * message, and a surface that renders fewer fails too — lowering the budget is
 * a change a reviewer should see and re-record, not a silent drift. A name that
 * the baseline forgot fails as well, so a newly instrumented surface cannot be
 * added without giving it a number.
 */
export function expectRenderBudget(budget: Record<string, number>): void {
  const collected = getCounts();
  for (const [surface, allowed] of Object.entries(budget)) {
    const actual = collected[surface] ?? 0;
    expect(actual, `${surface} renders ${actual}, budget is ${allowed}`).toBe(allowed);
  }
  const unbudgeted = Object.keys(collected).filter((surface) => !(surface in budget));
  expect(unbudgeted, "counted surfaces with no budget entry").toEqual([]);
}

/**
 * The four surfaces the budget pins, mounted inside the real providers and each
 * wrapped in its own counter. `App.tsx`'s nesting is kept, minus the update and
 * onboarding providers, which have no bearing on these three scenarios.
 */
export function CountedStudio({
  onStudio,
}: {
  onStudio: (studio: StudioContextValue) => void;
}): ReactNode {
  return (
    <StudioProvider>
      <BannerProvider>
        <StudioRuntimeProvider>
          <HandStudioBack onStudio={onStudio} />
          <CountedSurface id="composer">
            <ThreadComposer onCommand={ignoreCommand} />
          </CountedSurface>
          <CountedSurface id="landscape">
            <OpportunityLandscape />
          </CountedSurface>
          <CountedSurface id="rail">
            <WorkbenchRail />
          </CountedSurface>
          <CountedSurface id="banners">
            <BannerBridge />
            <BannerStack />
          </CountedSurface>
        </StudioRuntimeProvider>
      </BannerProvider>
    </StudioProvider>
  );
}

/**
 * A streamed reply of `count` deltas, then the message that closes it: the
 * cheapest way to make the store change `count` times without a network.
 */
export function streamOfDeltas(count: number): string {
  const deltas = Array.from(
    { length: count },
    (_unused, index) => `event: delta\ndata: {"text":"w${index} "}\n\n`,
  ).join("");
  return (
    'event: conversation\ndata: {"id":"c-2","title":"hello"}\n\n' +
    deltas +
    'event: message\ndata: {"content":"a streamed reply"}\n\n'
  );
}

/**
 * The composer keeps its own draft in the assistant-ui store, so typing is not
 * a `StudioContext` change: it has to be typed into the real control.
 */
export function typeIntoComposer(input: HTMLTextAreaElement, characters: number): void {
  for (let typed = 1; typed <= characters; typed += 1) {
    fireEvent.change(input, { target: { value: "x".repeat(typed) } });
  }
}

const ignoreCommand: (command: StudioCommand) => void = () => {};

function HandStudioBack({ onStudio }: { onStudio: (studio: StudioContextValue) => void }): ReactNode {
  const studio = useStudio();
  useEffect(() => {
    onStudio(studio);
  }, [onStudio, studio]);
  return null;
}
