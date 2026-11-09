import { describe, expect, it } from "vitest";

/**
 * The raw-colour gate (issue #543, parent #331).
 *
 * `theme.css` owns the palette. Everything else reads it through `var(--…)`,
 * so a colour written as a literal is a colour that does not follow the theme
 * and cannot be measured by `theme.test.ts`. This test is the thing that
 * notices a component inlining a hex value: it fails with the file and line,
 * so the next person can delete the literal instead of shipping it.
 *
 * `theme.css` is the one file allowed to hold literals — it is where the
 * tokens are defined. Files that legitimately sit outside the token system
 * (generated artwork, print media, SVG chart colour that encodes a score) are
 * named in `ALLOWED_FILES` with a reason and an issue. That list is a
 * baseline, not a licence: a new file with a literal fails, and an entry that
 * no longer has any literal fails too, so the list can only shrink.
 *
 * Rendered contrast is a separate gate. `e2e/a11y.spec.ts` measures what the
 * browser actually paints, including inside the allowed files, so a literal
 * that is unreadable still fails the build even here.
 */

/** Files whose literals are structural, each with the reason it is allowed. */
const ALLOWED_FILES: Record<string, { reason: string; issue: number }> = {
  "src/components/OdiMascot.tsx": {
    reason: "Generated brand artwork; brand/tools/render.py --check gates its pixels.",
    issue: 321,
  },
  "src/styles/print.css": {
    reason: "Print media. Paper is opaque black on white; the theme tokens describe screens.",
    issue: 331,
  },
  "src/onboarding/onboarding.css": {
    reason: "The first-run introduction is a fixed dark scrim with its own gradients.",
    issue: 330,
  },
  "src/components/canvas/OpportunityLandscape.tsx": {
    reason: "SVG chart colour encodes the score band; it is data, not theme.",
    issue: 335,
  },
  "src/components/canvas/JobMap.tsx": {
    reason: "SVG job-map strokes and fills are structural geometry, not theme.",
    issue: 335,
  },
};

/** The palette's own home; it is the one file that may hold literals. */
const TOKEN_FILE = "src/styles/theme.css";

/** Above this the baseline has become a dumping ground rather than a record. */
const ALLOWED_CAP = 6;

/** Source text for every file the gate reads, loaded the way Vite serves it. */
const SOURCES = {
  ...(import.meta.glob("/src/**/*.{ts,tsx}", {
    query: "?raw",
    import: "default",
    eager: true,
  }) as Record<string, string>),
  ...(import.meta.glob("/src/**/*.css", {
    query: "?raw",
    import: "default",
    eager: true,
  }) as Record<string, string>),
};

const HEX = "#[0-9a-fA-F]{3,8}\\b";
const FUNCTIONAL = "\\brgba?\\([^)]*\\)|\\bhsla?\\([^)]*\\)";
const COLOR = new RegExp(`${HEX}|${FUNCTIONAL}`, "g");

const WORD = /[0-9A-Za-z_]/;

/**
 * Whether a `#` at `index` sits where a colour would, rather than inside prose.
 *
 * A colour is written after a delimiter — `:`, `,`, `(`, a quote, or the start
 * of a value — so the `#` is never glued to a word. An issue reference in a
 * sentence ("Gong call #104") is: the `#` follows a word across a space. This
 * rejects that shape without needing a list of reference numbers.
 */
function inColorPosition(masked: string, index: number): boolean {
  const before = masked[index - 1];
  if (before !== undefined && WORD.test(before)) {
    return false;
  }
  // A `#` separated from a word only by whitespace is prose, not a value.
  let cursor = index - 1;
  while (cursor >= 0 && /\s/.test(masked[cursor])) {
    cursor -= 1;
  }
  if (cursor >= 0 && WORD.test(masked[cursor])) {
    return false;
  }
  return true;
}

/**
 * Blank out comments while keeping every other character, and every newline,
 * in place — so a match index still maps to the line the literal is on.
 *
 * A small state machine walks strings too: `"https://…"` is not a comment, and
 * a `//` inside it must not swallow the rest of the line.
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
  literal: string;
}

/** Every colour literal in a file, as `file:line literal`. */
function colorLiterals(file: string, source: string): Finding[] {
  const masked = maskComments(source);
  const found: Finding[] = [];
  for (const match of masked.matchAll(COLOR)) {
    const index = match.index ?? 0;
    const literal = match[0];
    if (literal.startsWith("#") && !inColorPosition(masked, index)) {
      continue;
    }
    // A template placeholder is a computed value, not a literal colour: the
    // contrast walker builds `rgb(${…}, ${…}, ${…})` from measured channels.
    if (literal.includes("${")) {
      continue;
    }
    const line = masked.slice(0, index).split("\n").length;
    // Report the original text, not the space-masked copy.
    found.push({ file, line, literal: source.slice(index, index + literal.length) });
  }
  return found;
}

const scanned = Object.entries(SOURCES)
  .filter(([file]) => !/\.(test|spec)\./.test(file))
  .filter(([file]) => file.replace(/^\//, "") !== TOKEN_FILE);

const findings = scanned.flatMap(([file, source]) =>
  colorLiterals(file.replace(/^\//, ""), source),
);
const byFile = new Map<string, Finding[]>();
for (const finding of findings) {
  byFile.set(finding.file, [...(byFile.get(finding.file) ?? []), finding]);
}

describe("raw colours", () => {
  it("keeps the palette in theme.css and nothing else", () => {
    const offenders = findings
      .filter((finding) => !(finding.file in ALLOWED_FILES))
      .map((finding) => `${finding.file}:${finding.line} ${finding.literal}`);

    expect(offenders).toEqual([]);
  });

  it("reads the whole source tree, so a new file cannot escape the scan", () => {
    // A regression in the glob (a typo in the pattern) would otherwise make
    // this test pass by scanning nothing.
    expect(scanned.length).toBeGreaterThan(100);
    expect(byFile.size).toBeGreaterThan(0);
  });

  it("caps the baseline so it cannot become a dumping ground", () => {
    expect(Object.keys(ALLOWED_FILES).length).toBeLessThanOrEqual(ALLOWED_CAP);
  });

  it("gives every allowed file a reason and an issue", () => {
    for (const [file, entry] of Object.entries(ALLOWED_FILES)) {
      expect(entry.reason, `${file} needs a reason`).not.toBe("");
      expect(entry.issue, `${file} needs an issue number`).toBeGreaterThan(0);
    }
  });

  it("fails on a stale entry, so the baseline can only shrink", () => {
    const stale = Object.keys(ALLOWED_FILES).filter((file) => !byFile.has(file));
    expect(stale).toEqual([]);
  });

  it("names the file and line for a colour that is not a token", () => {
    // The failure mode the issue asks for, proven against a literal that is
    // deliberately not in the baseline.
    expect(colorLiterals("src/components/Example.tsx", "const c = '#ff00ff';")).toEqual([
      { file: "src/components/Example.tsx", line: 1, literal: "#ff00ff" },
    ]);
  });

  it("ignores a colour that is only mentioned in a comment", () => {
    expect(colorLiterals("src/a.ts", "// see #ff00ff in the design\nconst x = 1;")).toEqual([]);
    expect(colorLiterals("src/a.ts", "/* rgba(0,0,0,0.5) */\n")).toEqual([]);
  });

  it("does not mistake a URL for a comment that hides a literal", () => {
    const source = 'const u = "https://example.com"; const c = "#123456";';
    expect(colorLiterals("src/a.ts", source)).toEqual([
      { file: "src/a.ts", line: 1, literal: "#123456" },
    ]);
  });
});
