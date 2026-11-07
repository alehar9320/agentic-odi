/// <reference types="node" />
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * The signal inbox is evidence-first: every card is a change the store
 * recorded. A previous developer affordance could inject fabricated signals
 * into the running app (#78, #322). This guard fails if that path returns.
 */

const here = (relative: string): string =>
  readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

const sources = [
  here("./CatchUpFeed.tsx"),
  here("../../state/StudioContext.tsx"),
  here("../../types.ts"),
];

describe("no fabricated signals", () => {
  it("has no simulator or its ids anywhere in production sources", () => {
    for (const source of sources) {
      expect(source).not.toMatch(/simulateBackgroundEvent/);
      expect(source).not.toMatch(/SIMULATED_SIGNAL_PREFIX/);
      expect(source).not.toMatch(/\bsimulated\b/);
    }
  });

  it("keeps the demo signals out of the app graph", () => {
    expect(here("./__fixtures__/signals.ts")).toMatch(/DEMO_SIGNALS/);
    for (const source of sources) {
      expect(source).not.toMatch(/__fixtures__\/signals/);
    }
  });

  it("ships no fabricated measurement in production sources", () => {
    for (const source of sources) {
      expect(source).not.toMatch(/82% of users/);
      expect(source).not.toMatch(/Simulate update/);
    }
  });
});
