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

import themeCss from "./theme.css?raw";
import { LIGHT_QUERY } from "../lib/theme";
import { inlineTag, tokenValue } from "../test/paletteTokens";
import { restoreMatchMedia, stubPrefersColorScheme } from "../test/prefersColorScheme";

// Vitest runs with the studio package as its working directory.
const html = readFileSync(join(process.cwd(), "index.html"), "utf8");

const inlineStyle = inlineTag(html, "style");
const inlineScript = inlineTag(html, "script");

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
  it("copies the dark --bg and --line from theme.css", () => {
    expect(tokenValue(inlineStyle, ":root", "boot-bg")).toBe(tokenValue(themeCss, ":root {", "bg"));
    expect(tokenValue(inlineStyle, ":root", "boot-line")).toBe(tokenValue(themeCss, ":root {", "line"));
  });

  it("copies the light --bg and --line from theme.css", () => {
    expect(tokenValue(inlineStyle, "html.theme-light", "boot-bg")).toBe(tokenValue(themeCss, "html.theme-light", "bg"));
    expect(tokenValue(inlineStyle, "html.theme-light", "boot-line")).toBe(tokenValue(themeCss, "html.theme-light", "line"));
  });

  it("resolves the dark class to the dark tokens", () => {
    // Dark is the `:root` default; `html:not(.theme-dark)` in the media block
    // keeps a resolved dark class from being overridden by a light system.
    expect(tokenValue(inlineStyle, ":root", "boot-bg")).toBe(tokenValue(themeCss, ":root {", "bg"));
    expect(tokenValue(inlineStyle, ":root", "boot-line")).toBe(tokenValue(themeCss, ":root {", "line"));
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
  function runScript(options: { stored?: string | null; prefersLight: boolean }): void {
    window.localStorage.clear();
    if (options.stored != null) {
      window.localStorage.setItem("studio.settings", options.stored);
    }
    stubPrefersColorScheme(options.prefersLight);
    document.documentElement.className = "";
    document.documentElement.removeAttribute("style");
    // The script is the one the browser runs before the bundle; executing it
    // here is what makes this a test of the resolution and not of its text.
    new Function(inlineScript)();
  }

  afterEach(() => {
    restoreMatchMedia();
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

  it("falls back to the media query when the stored value is unusable", () => {
    runScript({ stored: "{ not json", prefersLight: true });
    expect(document.documentElement.classList.contains("theme-light")).toBe(true);

    runScript({ stored: JSON.stringify({ theme: "sepia" }), prefersLight: false });
    expect(document.documentElement.classList.contains("theme-dark")).toBe(true);
  });

  it("reads a stored system choice as no palette at all", () => {
    // The app's `resolveTheme` treats "system" exactly like no value at all. The
    // bootstrap accepts only the two literals, so both reach the media query and
    // paint the same class — the handover from this script to the bundle changes
    // nothing. A change here that made the bootstrap read "system" as a palette
    // would flash the wrong colour on every cold load for a reader following the
    // operating system.
    runScript({ stored: JSON.stringify({ theme: "system" }), prefersLight: true });
    expect(document.documentElement.classList.contains("theme-light")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("light");

    runScript({ stored: JSON.stringify({ theme: "system" }), prefersLight: false });
    expect(document.documentElement.classList.contains("theme-dark")).toBe(true);
  });

  it("asks the operating system the same question the app asks", () => {
    // One query string, two callers. If they drifted, the class painted here and
    // the palette `useSystemTheme` subscribes to would be answers to different
    // questions.
    expect(inlineScript).toContain(LIGHT_QUERY);
  });

  it("is plain and synchronous, so nothing can defer it", () => {
    expect(inlineScript).not.toMatch(/\bimport\b/);
    expect(inlineScript).not.toMatch(/async|defer/);
  });

  it("declares both colour schemes so native controls follow the class", () => {
    expect(html).toContain('<meta name="color-scheme" content="dark light"');
  });

  it("tells the browser chrome the same two colours", () => {
    expect(html).toContain(`<meta name="theme-color" content="${tokenValue(themeCss, ":root {", "bg")}" />`);
    expect(html).toContain(
      `<meta name="theme-color" content="${tokenValue(themeCss, "html.theme-light", "bg")}" media="(prefers-color-scheme: light)" />`,
    );
  });
});
