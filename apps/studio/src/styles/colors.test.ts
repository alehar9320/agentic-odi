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
};

/** The palette's own home; it is the one file that may hold literals. */
const TOKEN_FILE = "src/styles/theme.css";

/** Above this the baseline has become a dumping ground rather than a record.
 * 4 since the job map's pipeline tiles moved onto the palette: the file had no
 * literal left, so its #335 excuse went with them. */
const ALLOWED_CAP = 4;

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

/* ------------------------------------------------------------------ */
/* The palette file itself (#543's sibling, ALH-216)                   */
/* ------------------------------------------------------------------ */

/**
 * `theme.css` is exempt from the tree scan because it is where the palette
 * lives. That exemption was written for the token blocks, and the file has
 * grown rules around them: a literal inside a rule cannot follow the theme —
 * `html.theme-light` appears once in the file, at the token block — so it
 * cannot be measured by `theme.test.ts` either, and it drifts.
 *
 * These helpers read the file's declarations and split its literals in two.
 * An **opaque** value in a rule is a bug at zero tolerance: it is a colour that
 * will be wrong in the other palette. An **alpha** value is a wash whose
 * severity is proportional to its transparency, and is held to a count that can
 * only shrink.
 */

/** The palette file's own text. */
const themeSource = SOURCES[`/${TOKEN_FILE}`];

/**
 * Line ranges of the blocks that define the palette: `:root`,
 * `html.theme-light`, and any later `:root` that adds tokens. The only places a
 * colour literal is legal.
 */
function tokenBlocks(source: string): Array<[number, number]> {
  const masked = maskComments(source);
  const lines = masked.split("\n");
  const blocks: Array<[number, number]> = [];
  let depth = 0;
  let opened = 0;
  lines.forEach((line, index) => {
    if (depth === 0 && /^(?::root|html\.theme-light)\s*\{/.test(line)) {
      opened = index + 1;
    }
    depth += (line.match(/\{/g) ?? []).length - (line.match(/\}/g) ?? []).length;
    if (opened && depth === 0) {
      blocks.push([opened, index + 1]);
      opened = 0;
    }
  });
  return blocks;
}

interface Declaration {
  /** Offset just past the colon, where the value begins. */
  from: number;
  /** Offset of the terminator that ends the value. */
  to: number;
  property: string;
  value: string;
}

/** Every `property: value;` in the stylesheet, at any nesting depth. */
function declarations(masked: string): Declaration[] {
  const out: Declaration[] = [];
  let cursor = 0;
  while (cursor < masked.length) {
    const semicolon = masked.indexOf(";", cursor);
    const open = masked.indexOf("{", cursor);
    const close = masked.indexOf("}", cursor);
    const stops = [semicolon, open, close].filter((index) => index >= 0);
    if (stops.length === 0) {
      break;
    }
    const stop = Math.min(...stops);
    if (masked[stop] === ";") {
      const chunk = masked.slice(cursor, stop);
      const colon = chunk.indexOf(":");
      if (colon >= 0) {
        const property = chunk.slice(0, colon).trim();
        if (/^[a-z-]+$/.test(property)) {
          out.push({
            from: cursor + colon + 1,
            to: stop,
            property,
            value: chunk.slice(colon + 1),
          });
        }
      }
    }
    cursor = stop + 1;
  }
  return out;
}

/** How see-through a colour literal is: 1 is solid ink. */
function alphaOf(literal: string): number {
  if (literal.startsWith("#")) {
    if (literal.length === 9 || literal.length === 5) {
      const alpha = parseInt(literal.slice(literal.length - 2), 16);
      return Number.isNaN(alpha) ? 1 : alpha / 255;
    }
    return 1;
  }
  const parts = literal
    .slice(literal.indexOf("(") + 1, literal.lastIndexOf(")"))
    .split(/[\s,/]+/)
    .filter(Boolean);
  if (parts.length < 4) {
    return 1;
  }
  const last = parts[parts.length - 1];
  return last.endsWith("%") ? parseFloat(last) / 100 : parseFloat(last);
}

/** Which line of the source an offset falls on. */
function lineOf(masked: string, index: number): number {
  return masked.slice(0, index).split("\n").length;
}

/** Colour literals in the palette file's rules, filtered by how solid they are. */
function paletteLiterals(
  source: string,
  keep: (alpha: number) => boolean,
): Array<Finding & { property: string }> {
  const masked = maskComments(source);
  const blocks = tokenBlocks(source);
  const out: Array<Finding & { property: string }> = [];
  for (const declaration of declarations(masked)) {
    const declaredAt = lineOf(masked, declaration.from);
    if (blocks.some(([first, last]) => declaredAt >= first && declaredAt <= last)) {
      continue;
    }
    const body = masked.slice(declaration.from, declaration.to);
    for (const match of body.matchAll(COLOR)) {
      const index = declaration.from + (match.index ?? 0);
      const literal = match[0];
      if (literal.startsWith("#") && !inColorPosition(masked, index)) {
        continue;
      }
      if (!keep(alphaOf(literal))) {
        continue;
      }
      out.push({
        file: TOKEN_FILE,
        line: lineOf(masked, index),
        literal: source.slice(index, index + literal.length),
        property: declaration.property,
      });
    }
  }
  return out;
}

const isOpaque = (alpha: number): boolean => alpha >= 1;
const isWash = (alpha: number): boolean => alpha < 1;

/** Solid colour in a rule, where only a token can follow the theme. */
function opaqueOutsideTokens(source: string): Array<Finding & { property: string }> {
  return paletteLiterals(source, isOpaque);
}

/** Translucent wash in a rule: less wrong, still worth a number. */
function alphaOutsideTokens(source: string): Array<Finding & { property: string }> {
  return paletteLiterals(source, isWash);
}

/** How the gate reports a site, so a failure reads as a checklist. */
function row(finding: Finding & { property: string }): string {
  return `${finding.file}:${finding.line} ${finding.property}: ${finding.literal}`;
}

/**
 * Solid colour written into a rule instead of read from a token. Zero is the
 * only honest ceiling: the value cannot change with the theme, so a non-zero
 * ceiling is a list of light-theme defects with a number on it.
 */
const OPAQUE_CEILING = 0;

/**
 * Measured 2026-11-05, per literal rather than per line. Exact rather than a
 * ceiling, so the number moves only when someone converts a wash and banks the
 * new count here — the same one-way ratchet the `ALLOWED_FILES` staleness test
 * runs on. 208 at the themed-surface work's start; the opportunity map and the
 * changelog chip moved onto the tint tokens and banked the four that left.
 */
const ALPHA_BASELINE = 204;

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

  /* --- the palette file's own rules (ALH-216) --------------------- */

  it("refuses an opaque colour literal in the palette file's own rules", () => {
    const found = opaqueOutsideTokens(themeSource);
    expect(found.length).toBeLessThanOrEqual(OPAQUE_CEILING);
    // The rows are the answer: a failure here prints every site at once, which
    // is the list the migration works down.
    expect(found.map(row)).toEqual([]);
  });

  it("keeps the palette file's alpha washes at a baseline that can only move by being banked", () => {
    expect(alphaOutsideTokens(themeSource).length).toBe(ALPHA_BASELINE);
  });

  it("names the line for a literal injected into the palette file, and not one inside a token block", () => {
    // The issue's own requirement, aimed at the file the tree scan exempts.
    const source = ":root {\n  --swatch: #ff00ff;\n}\n.card {\n  color: #ff00fe;\n}\n";
    expect(opaqueOutsideTokens(source).map((finding) => finding.line)).toEqual([5]);
    expect(opaqueOutsideTokens(source).map(row)).toEqual([
      "src/styles/theme.css:5 color: #ff00fe",
    ]);
  });

  it("reads a literal nested in a gradient or hiding in a var() fallback", () => {
    const source =
      ".a {\n  background: linear-gradient(140deg, #6366f1, transparent);\n}\n" +
      ".b {\n  background: var(--odi-tile, #131722);\n}\n";
    expect(opaqueOutsideTokens(source).map(row)).toEqual([
      "src/styles/theme.css:2 background: #6366f1",
      "src/styles/theme.css:5 background: #131722",
    ]);
  });

  it("exempts the token blocks because it found them, not because they were listed", () => {
    const selectors = Array.from(
      themeSource.matchAll(/^(?::root|html\.theme-light)\s*\{/gm),
      (match) => match[0].trim(),
    );
    expect(tokenBlocks(themeSource)).toHaveLength(selectors.length);
    // The whole drift this gate exists to close rests on this: the light palette
    // is one declaration block, so every rule below it is theme-blind.
    expect(selectors.filter((selector) => selector.startsWith("html.theme-light"))).toHaveLength(1);
  });
});
