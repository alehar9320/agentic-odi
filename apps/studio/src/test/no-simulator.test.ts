import { build } from "vite";
import { describe, expect, it } from "vitest";

/**
 * The simulator was deleted in #322. Two guards keep it deleted: a source scan
 * that fails if any of its identifiers come back, and a real production build
 * that must not contain the strings it fabricated.
 */

/** Production sources, loaded through Vite so the scan has no node typings. */
const SOURCES = import.meta.glob("/src/**/*.{ts,tsx}", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const PRODUCTION_SOURCES = Object.entries(SOURCES).filter(
  ([file]) => !file.includes(".test.") && !file.includes("__fixtures__"),
);

describe("the developer simulator stays deleted", () => {
  it("has no source file that names the simulator, its prefix, or a simulated field", () => {
    const forbidden = [/simulateBackgroundEvent/, /SIMULATED_SIGNAL_PREFIX/, /\.simulated\b/, /simulated\?/];
    const offenders = PRODUCTION_SOURCES.flatMap(([file, text]) =>
      forbidden
        .filter((pattern) => pattern.test(text))
        .map((pattern) => `${file} matches ${pattern}`),
    );

    expect(offenders).toEqual([]);
  });

  it("does not ship the simulator or its fabricated strings in the production bundle", async () => {
    const result = await build({
      configFile: "vite.config.ts",
      logLevel: "silent",
      build: { write: false },
    });

    const outputs = Array.isArray(result) ? result : [result];
    const code = outputs
      .flatMap((output) => ("output" in output ? output.output : []))
      .map((chunk) => ("code" in chunk ? chunk.code : ""))
      .join("\n");

    // Prove the build actually produced the app before trusting the absences.
    expect(code).toContain("Signal inbox");
    expect(code).not.toContain("Simulate update");
    expect(code).not.toContain("82% of users");
  }, 60_000);
});
