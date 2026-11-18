import { describe, expect, it } from "vitest";

/**
 * The opportunity-score ratchet (issue #1087).
 *
 * `packages/core` owns the ODI arithmetic and ships a fixture
 * (`packages/core/tests/fixtures/opportunity-score.json`) that
 * `lib/odi.test.ts` checks the browser's `opportunityScore` against. The
 * browser then kept four more copies of the same formula: the offline store,
 * the chat orchestrator, and two tests. Nothing compared them, so a rounding
 * change in one copy could disagree with the fixture while every test still
 * passed.
 *
 * This test is the thing that notices the fifth copy: it fails with the file
 * and line, so the next person imports `opportunityScore` instead of shipping
 * another arithmetic. `src/lib/odi.ts` is the one file allowed to hold the
 * formula — it is the declared owner.
 *
 * A bare `Math.max(importance - satisfaction, 0)` is not the score: it is the
 * gap, and `ScorePopover` computes it for the meter it draws. The scan matches
 * the whole formula (`importance + Math.max(importance - satisfaction, …)`), so
 * the gap is free to be computed where it is displayed.
 */

/** The one file that owns the arithmetic. */
const OWNER_FILE = "src/lib/odi.ts";

/** The full formula, tolerant of the whitespace a formatter may introduce. */
const FORMULA = /importance\s*\+\s*Math\.max\(\s*importance\s*-\s*satisfaction/g;

/** Source text for every file the gate reads, loaded the way Vite serves it. */
const SOURCES = import.meta.glob("/src/**/*.{ts,tsx}", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/**
 * Blank out comments while keeping every other character, and every newline,
 * in place — so a match index still maps to the line the formula is on. A
 * formula quoted in prose ("the score is importance + max(…)") is
 * documentation, not a second implementation.
 */
function maskComments(source: string): string {
  const out = source.split("");
  type State = "code" | "line" | "block" | "single" | "double" | "template";
  let state: State = "code";
  let i = 0;
  while (i < source.length) {
    const char = source[i];
    const next = source[i + 1];
    if (state === "code") {
      if (char === "/" && next === "/") {
        out[i] = " ";
        out[i + 1] = " ";
        state = "line";
        i += 2;
        continue;
      }
      if (char === "/" && next === "*") {
        out[i] = " ";
        out[i + 1] = " ";
        state = "block";
        i += 2;
        continue;
      }
      if (char === "'") state = "single";
      else if (char === '"') state = "double";
      else if (char === "`") state = "template";
      i += 1;
      continue;
    }
    if (state === "line") {
      if (char === "\n") state = "code";
      else out[i] = " ";
      i += 1;
      continue;
    }
    if (state === "block") {
      if (char === "*" && next === "/") {
        out[i] = " ";
        out[i + 1] = " ";
        state = "code";
        i += 2;
        continue;
      }
      if (char !== "\n") out[i] = " ";
      i += 1;
      continue;
    }
    // Inside a string literal: only the closing quote (or an escape) matters.
    const quote = state === "single" ? "'" : state === "double" ? '"' : "`";
    if (char === "\\") {
      i += 2;
      continue;
    }
    if (char === quote) state = "code";
    i += 1;
  }
  return out.join("");
}

interface Finding {
  file: string;
  line: number;
}

/** Every copy of the formula in a file, as `file:line`. */
function formulaCopies(file: string, source: string): Finding[] {
  const masked = maskComments(source);
  const found: Finding[] = [];
  for (const match of masked.matchAll(FORMULA)) {
    const index = match.index ?? 0;
    const line = masked.slice(0, index).split("\n").length;
    found.push({ file, line });
  }
  return found;
}

/**
 * The scanner's own file quotes the formula in its example strings. Vite's glob
 * already omits the importing module, and this filter keeps that explicit so a
 * bundler change cannot make the test flag its own fixtures as a second copy.
 */
const SCANNER_FILE = "src/lib/formula.test.ts";

const scanned = Object.entries(SOURCES)
  .filter(([file]) => file.replace(/^\//, "") !== SCANNER_FILE)
  .map(([file, source]) => formulaCopies(file.replace(/^\//, ""), source));
const findings = scanned.flat();

describe("the opportunity-score formula", () => {
  it("has exactly one owner", () => {
    const offenders = findings
      .filter((finding) => finding.file !== OWNER_FILE)
      .map((finding) => `${finding.file}:${finding.line}`);

    expect(offenders).toEqual([]);
  });

  it("reads the whole source tree, so a new file cannot escape the scan", () => {
    // A regression in the glob (a typo in the pattern) would otherwise make
    // this test pass by scanning nothing.
    expect(scanned.length).toBeGreaterThan(100);
    expect(findings.length).toBeGreaterThan(0);
  });

  it("names the file and line for a copy outside the owner", () => {
    // The failure mode the issue asks for, proven against a literal that is
    // deliberately not in the source tree.
    expect(
      formulaCopies("src/components/Example.ts", "const s = importance + Math.max(importance - satisfaction, 0);"),
    ).toEqual([{ file: "src/components/Example.ts", line: 1 }]);
  });

  it("ignores the formula when it is only quoted in a comment", () => {
    expect(
      formulaCopies(
        "src/a.ts",
        "// score = importance + Math.max(importance - satisfaction, 0)\nconst x = 1;",
      ),
    ).toEqual([]);
  });

  it("leaves the gap computation alone", () => {
    // `Math.max(importance - satisfaction, 0)` is the gap a meter draws, not
    // a second implementation of the score.
    expect(
      formulaCopies("src/a.ts", "const gap = Math.max(importance - satisfaction, 0);"),
    ).toEqual([]);
  });
});