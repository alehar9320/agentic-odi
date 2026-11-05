/**
 * The offline one-pager (ALH-216).
 *
 * `public/offline.html` is the only page a reader can reach with no server, and
 * it is a hand-written copy of the palette: it cannot import `theme.css`,
 * because an import is a request. That is how it drifted — `--line` sat at twice
 * the theme's alpha, and the resolver read a stored `"system"` as the dark
 * palette, so a reader following the operating system on a light machine got a
 * black sheet.
 *
 * These tests hold the copy against the source and run the shipped resolver in
 * jsdom, so the claim being tested is the resolution and not its text.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import themeCss from "./theme.css?raw";
import { LIGHT_QUERY } from "../lib/theme";
import { colorTokens, inlineTag, tokenValue } from "../test/paletteTokens";
import { restoreMatchMedia, stubPrefersColorScheme } from "../test/prefersColorScheme";

// Vitest runs with the studio package as its working directory.
const html = readFileSync(join(process.cwd(), "public/offline.html"), "utf8");
const style = inlineTag(html, "style");
const script = inlineTag(html, "script");

/** The offline block and the palette block it is supposed to copy. */
const BLOCKS = [
  ["dark", ":root", ":root {"],
  ["light", 'html[data-theme="light"]', "html.theme-light"],
] as const;

describe("the offline palette", () => {
  it("copies the palette rather than inventing one", () => {
    const drift: string[] = [];
    for (const [theme, offlineSelector, paletteSelector] of BLOCKS) {
      const shipped = colorTokens(style, offlineSelector);
      expect(Object.keys(shipped).length, `the ${theme} block declares no tokens`).toBeGreaterThan(
        0,
      );
      for (const [name, value] of Object.entries(shipped)) {
        // A token the palette declares once for both themes — the filled
        // control's pair is one — resolves from `:root` in light as it does on
        // this page, so falling back is the same answer CSS gives.
        const source =
          tokenValue(themeCss, paletteSelector, name) ?? tokenValue(themeCss, ":root {", name);
        if (source === null) {
          drift.push(`--${name} (${theme}): the offline page declares it, theme.css does not`);
        } else if (source !== value) {
          drift.push(
            `--${name} (${theme}): ${value} on the offline page, ${source} in the palette`,
          );
        }
      }
    }
    expect(drift).toEqual([]);
  });

  it("paints a filled control with the pair the contrast gate measured", () => {
    // `--accent-strong` is a word's colour; `--accent-fill` is a surface's, and
    // it ships with the ink that clears 4.5:1 against it. On the dark side the
    // difference is 4.47:1 against 6.07 — a button this page invites a tap on.
    const declarations = (selector: string): string => {
      const start = style.indexOf(`${selector} {`);
      expect(start, `the offline page styles no ${selector}`).toBeGreaterThanOrEqual(0);
      return style.slice(style.indexOf("{", start) + 1, style.indexOf("}", start));
    };
    for (const selector of [".wordmark__mark", ".action"]) {
      const rule = declarations(selector);
      expect(rule).toContain("background: var(--accent-fill)");
      expect(rule).toContain("color: var(--on-accent)");
    }
    expect(style).not.toMatch(/background:\s*#fff|color:\s*#fff|color:\s*white/);
  });

  it("needs no server to paint", () => {
    expect(style).not.toMatch(/url\(|@import|@font-face/);
    expect(html).not.toMatch(/<link\b/);
    expect(html).not.toMatch(/<\w+[^>]*\ssrc=/);
    expect(html).not.toMatch(/fetch\(|https?:\/\//);
    // A cold miss that tried to fetch its own theme would show a spinner, not a
    // page. The only link on it is the one back to the app.
    expect(html).toContain('<a class="action" href="/"');
  });
});

describe("the offline theme resolver", () => {
  function resolve(stored: string | null, prefersLight: boolean): string | undefined {
    window.localStorage.clear();
    if (stored !== null) {
      window.localStorage.setItem("studio.settings", stored);
    }
    stubPrefersColorScheme(prefersLight);
    delete document.documentElement.dataset.theme;
    // The script is this repository's own file, read off disk — running it here
    // is what makes this a test of the resolution and not of its text.
    new Function(script)();
    return document.documentElement.dataset.theme;
  }

  afterEach(() => {
    restoreMatchMedia();
    delete document.documentElement.dataset.theme;
    window.localStorage.clear();
  });

  it("reads a stored choice as the palette it names, whatever the system wants", () => {
    expect(resolve(JSON.stringify({ theme: "light" }), false)).toBe("light");
    expect(resolve(JSON.stringify({ theme: "dark" }), true)).toBe("dark");
  });

  it("follows the operating system for a reader who chose to", () => {
    // The three-branch rule in `resolveTheme`: a stored "system" is not a
    // palette, it is the question "what does the machine say?".
    expect(resolve(JSON.stringify({ theme: "system" }), true)).toBe("light");
    expect(resolve(JSON.stringify({ theme: "system" }), false)).toBe("dark");
  });

  it("follows the operating system when nothing was ever stored", () => {
    expect(resolve(null, true)).toBe("light");
    expect(resolve(null, false)).toBe("dark");
  });

  it("survives a stored value it cannot read", () => {
    expect(resolve("{ not json", true)).toBe("light");
    expect(resolve(JSON.stringify({ theme: "sepia" }), false)).toBe("dark");
  });

  it("sets a theme the page has a block for, and asks the same question the app asks", () => {
    expect(resolve(JSON.stringify({ theme: "system" }), true)).toBeTruthy();
    expect(style).toContain('html[data-theme="light"]');
    expect(script).toContain(LIGHT_QUERY);
  });

  it("runs before the paint, plainly and synchronously", () => {
    expect(html.indexOf("<script>")).toBeLessThan(html.indexOf("<style>"));
    expect(script).not.toMatch(/\bimport\b|async|defer|addEventListener/);
  });
});
