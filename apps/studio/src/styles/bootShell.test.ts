/**
 * Guards for the pre-JavaScript shell in `index.html`.
 *
 * The shell exists so a cold load is never the browser's white canvas. It can
 * only do that if it runs before the bundle, carries no request of its own, and
 * paints the same colours the app will. These tests read the document as
 * shipped and hold it to that contract; the colour check keeps the inline
 * literals in step with `theme.css`, which stays the source of truth.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import type { StudioTheme } from "../types";
import { resolveTheme } from "../lib/theme";
import paletteCss from "./tokens.css?raw";

// Vitest runs with the studio package as its working directory.
const html = readFileSync(join(process.cwd(), "index.html"), "utf8");

function readTag(tag: "style" | "script"): string {
  const match = html.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`));
  expect(match, `missing inline <${tag}>`).not.toBeNull();
  return match![1];
}

const inlineStyle = readTag("style");
const inlineScript = readTag("script");

/** The value of a custom property inside the first block matching `selector`. */
function bootToken(selector: string, token: string): string | null {
  const start = inlineStyle.indexOf(selector);
  if (start < 0) {
    return null;
  }
  const open = inlineStyle.indexOf("{", start);
  const block = inlineStyle.slice(open, inlineStyle.indexOf("}", open));
  return block.match(new RegExp(`--${token}:\\s*([^;]+);`))?.[1].trim() ?? null;
}

/** The value of a token inside a block of the palette. */
function paletteToken(selector: string, token: string): string | null {
  const start = paletteCss.indexOf(selector);
  const open = paletteCss.indexOf("{", start);
  const block = paletteCss.slice(open, paletteCss.indexOf("}", open));
  return block.match(new RegExp(`--${token}:\\s*([^;]+);`))?.[1].trim() ?? null;
}

describe("the bootstrap shell", () => {
  it("ships inside #root so React replaces it, and stays out of the a11y tree", () => {
    const root = html.match(/<div id="root">([\s\S]*?)<\/div>\s*<script type="module"/);
    expect(root).not.toBeNull();
    expect(root![1]).toContain('id="boot"');
    expect(root![1]).toMatch(/id="boot"[^>]*aria-hidden="true"/);
  });

  it("draws the bar, the rail, and the stage", () => {
    for (const part of ["bar", "rail", "stage"]) {
      expect(html).toContain(`class="boot-shell__${part}"`);
    }
  });

  it("requests neither a font nor an image", () => {
    expect(inlineStyle).not.toMatch(/url\(/);
    expect(inlineStyle).not.toMatch(/@font-face/);
    expect(inlineScript).not.toMatch(/url\(/);
  });

  it("stays a small bootstrap rather than a second stylesheet", () => {
    // #308 budgets the inline style at 1 KB; the script is a few hundred bytes.
    expect(inlineStyle.length).toBeLessThan(1024);
    expect(inlineStyle.length + inlineScript.length).toBeLessThan(2048);
  });
});

describe("the bootstrap colours", () => {
  it("copies the dark --bg and --line from the palette", () => {
    expect(bootToken(":root", "boot-bg")).toBe(paletteToken(":root {", "bg"));
    expect(bootToken(":root", "boot-line")).toBe(paletteToken(":root {", "line"));
  });

  it("copies the light --bg and --line from the palette", () => {
    expect(bootToken("html.theme-light", "boot-bg")).toBe(paletteToken("html.theme-light", "bg"));
    expect(bootToken("html.theme-light", "boot-line")).toBe(paletteToken("html.theme-light", "line"));
  });

  it("resolves the dark class to the dark tokens", () => {
    // Dark is the `:root` default; `html:not(.theme-dark)` in the media block
    // keeps a resolved dark class from being overridden by a light system.
    expect(bootToken(":root", "boot-bg")).toBe(paletteToken(":root {", "bg"));
    expect(bootToken(":root", "boot-line")).toBe(paletteToken(":root {", "line"));
  });

  it("follows the operating system before the script runs, without overriding a resolved class", () => {
    expect(inlineStyle).toMatch(/@media\s*\(prefers-color-scheme:\s*light\)/);
    // The resolved class is declared after the media block, so it wins the cascade.
    expect(inlineStyle.indexOf("html.theme-light")).toBeGreaterThan(
      inlineStyle.indexOf("@media (prefers-color-scheme: light)"),
    );
    expect(inlineStyle).toContain("html:not(.theme-dark)");
  });
});

describe("the inline theme script", () => {
  const originalMatchMedia = window.matchMedia;

  function runScript(options: { stored?: string | null; prefersLight: boolean }): void {
    window.localStorage.clear();
    if (options.stored != null) {
      window.localStorage.setItem("studio.settings", options.stored);
    }
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: (query: string) => ({
        matches: query.includes("prefers-color-scheme: light") ? options.prefersLight : false,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }),
    });
    document.documentElement.className = "";
    document.documentElement.removeAttribute("style");
    // The script is the one the browser runs before the bundle; executing it
    // here is what makes this a test of the resolution and not of its text.
    new Function(inlineScript)();
  }

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: originalMatchMedia,
    });
    document.documentElement.className = "";
    document.documentElement.removeAttribute("style");
    window.localStorage.clear();
  });

  it("applies the stored light theme before React, even when the system is dark", () => {
    runScript({ stored: JSON.stringify({ theme: "light" }), prefersLight: false });
    expect(document.documentElement.classList.contains("theme-light")).toBe(true);
    expect(document.documentElement.classList.contains("theme-dark")).toBe(false);
    expect(document.documentElement.style.colorScheme).toBe("light");
  });

  it("applies the stored dark theme even when the system is light", () => {
    runScript({ stored: JSON.stringify({ theme: "dark" }), prefersLight: true });
    expect(document.documentElement.classList.contains("theme-dark")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });

  it("follows the media query when nothing is stored", () => {
    runScript({ stored: null, prefersLight: true });
    expect(document.documentElement.classList.contains("theme-light")).toBe(true);

    runScript({ stored: null, prefersLight: false });
    expect(document.documentElement.classList.contains("theme-dark")).toBe(true);
  });

  it("paints a stored system choice from the operating system, before the bundle runs", () => {
    // ALH-201 makes "system" a choice the app offers, so the pre-paint script
    // may not treat it as an unknown value and let the app disagree after the
    // bundle takes over.
    runScript({ stored: JSON.stringify({ theme: "system" }), prefersLight: true });
    expect(document.documentElement.classList.contains("theme-light")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("light");

    runScript({ stored: JSON.stringify({ theme: "system" }), prefersLight: false });
    expect(document.documentElement.classList.contains("theme-dark")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });

  it("resolves the stored choice exactly the way the app resolves it", () => {
    // Two implementations of one decision — the script that paints and the app
    // that keeps painting — so this compares them across every value each side
    // can be handed rather than checking the script in isolation.
    for (const stored of ["light", "dark", "system", undefined]) {
      for (const prefersLight of [true, false]) {
        runScript({ stored: JSON.stringify({ theme: stored }), prefersLight });
        const painted = document.documentElement.classList.contains("theme-light")
          ? "light"
          : "dark";
        const expected = resolveTheme(stored as StudioTheme | undefined, prefersLight);
        expect(
          painted,
          `stored ${String(stored)} on a ${prefersLight ? "light" : "dark"} system`,
        ).toBe(expected);
      }
    }
  });

  it("falls back to the media query when the stored value is unusable", () => {
    runScript({ stored: "{ not json", prefersLight: true });
    expect(document.documentElement.classList.contains("theme-light")).toBe(true);

    runScript({ stored: JSON.stringify({ theme: "sepia" }), prefersLight: false });
    expect(document.documentElement.classList.contains("theme-dark")).toBe(true);
  });

  it("is plain and synchronous, so nothing can defer it", () => {
    expect(inlineScript).not.toMatch(/\bimport\b/);
    expect(inlineScript).not.toMatch(/async|defer/);
  });

  it("declares both colour schemes so native controls follow the class", () => {
    expect(html).toContain('<meta name="color-scheme" content="dark light"');
  });

  it("tells the browser chrome the same two colours", () => {
    expect(html).toContain(`<meta name="theme-color" content="${paletteToken(":root {", "bg")}" />`);
    expect(html).toContain(
      `<meta name="theme-color" content="${paletteToken("html.theme-light", "bg")}" media="(prefers-color-scheme: light)" />`,
    );
  });
});
