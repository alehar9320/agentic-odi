/**
 * Guards for the pre-JavaScript shell in `index.html`.
 *
 * The shell exists so a cold load is never the browser's white canvas. It can
 * only do that if it runs before the bundle, carries no request of its own, and
 * paints the same colours the app will. These tests read the document as
 * shipped and hold it to that contract; the colour check keeps the literals in
 * `public/boot.css` in step with `theme.css`, which stays the source of truth.
 *
 * Both bootstraps are same-origin files rather than inline blocks. The sidecar
 * (`CSP_POLICY` in the studio API) and the Tauri window serve this document
 * under `script-src 'self'; style-src 'self'`, so an inline `<style>` or
 * `<script>` is refused by the browser and the shell paints nothing at all.
 * "No inline script or style" is therefore part of the contract these tests
 * hold, not a matter of taste.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import themeCss from "./theme.css?raw";

// Vitest runs with the studio package as its working directory.
const html = readFileSync(join(process.cwd(), "index.html"), "utf8");
const bootCss = readFileSync(join(process.cwd(), "public", "boot.css"), "utf8");
const themeScript = readFileSync(join(process.cwd(), "public", "boot-theme.js"), "utf8");

/** The value of a custom property inside the first block matching `selector`. */
function bootToken(selector: string, token: string): string | null {
  const start = bootCss.indexOf(selector);
  if (start < 0) {
    return null;
  }
  const open = bootCss.indexOf("{", start);
  const block = bootCss.slice(open, bootCss.indexOf("}", open));
  return block.match(new RegExp(`--${token}:\\s*([^;]+);`))?.[1].trim() ?? null;
}

/** The value of a token inside a block of `theme.css`. */
function themeToken(selector: string, token: string): string | null {
  const start = themeCss.indexOf(selector);
  const open = themeCss.indexOf("{", start);
  const block = themeCss.slice(open, themeCss.indexOf("}", open));
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

  it("keeps the document free of inline script and style, so the strict CSP can serve it", () => {
    expect(html).not.toMatch(/<style[\s>]/i);
    for (const tag of html.match(/<script\b[^>]*>/gi) ?? []) {
      expect(tag, `inline script would be refused by the CSP: ${tag}`).toMatch(/\bsrc="/);
    }
  });

  it("loads both bootstraps from same-origin files that exist", () => {
    expect(html).toContain('<link rel="stylesheet" href="/boot.css" />');
    expect(html).toContain('<script src="/boot-theme.js"></script>');
    expect(existsSync(join(process.cwd(), "public", "boot.css"))).toBe(true);
    expect(existsSync(join(process.cwd(), "public", "boot-theme.js"))).toBe(true);
  });

  it("requests neither a font nor an image", () => {
    expect(bootCss).not.toMatch(/url\(/);
    expect(bootCss).not.toMatch(/@font-face/);
    expect(themeScript).not.toMatch(/url\(/);
  });

  it("stays a small bootstrap rather than a second stylesheet", () => {
    // #308 budgets the boot style at 1 KB; the script is a few hundred bytes.
    expect(bootCss.length).toBeLessThan(1024);
    expect(bootCss.length + themeScript.length).toBeLessThan(2048);
  });
});

describe("the bootstrap colours", () => {
  it("copies the dark --bg and --line from theme.css", () => {
    expect(bootToken(":root", "boot-bg")).toBe(themeToken(":root {", "bg"));
    expect(bootToken(":root", "boot-line")).toBe(themeToken(":root {", "line"));
  });

  it("copies the light --bg and --line from theme.css", () => {
    expect(bootToken("html.theme-light", "boot-bg")).toBe(themeToken("html.theme-light", "bg"));
    expect(bootToken("html.theme-light", "boot-line")).toBe(themeToken("html.theme-light", "line"));
  });

  it("resolves the dark class to the dark tokens", () => {
    // Dark is the `:root` default; `html:not(.theme-dark)` in the media block
    // keeps a resolved dark class from being overridden by a light system.
    expect(bootToken(":root", "boot-bg")).toBe(themeToken(":root {", "bg"));
    expect(bootToken(":root", "boot-line")).toBe(themeToken(":root {", "line"));
  });

  it("follows the operating system before the script runs, without overriding a resolved class", () => {
    expect(bootCss).toMatch(/@media\s*\(prefers-color-scheme:\s*light\)/);
    // The resolved class is declared after the media block, so it wins the cascade.
    expect(bootCss.indexOf("html.theme-light")).toBeGreaterThan(
      bootCss.indexOf("@media (prefers-color-scheme: light)"),
    );
    expect(bootCss).toContain("html:not(.theme-dark)");
  });
});

describe("the theme bootstrap script", () => {
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
    new Function(themeScript)();
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

  it("falls back to the media query when the stored value is unusable", () => {
    runScript({ stored: "{ not json", prefersLight: true });
    expect(document.documentElement.classList.contains("theme-light")).toBe(true);

    runScript({ stored: JSON.stringify({ theme: "sepia" }), prefersLight: false });
    expect(document.documentElement.classList.contains("theme-dark")).toBe(true);
  });

  it("is plain and synchronous, so nothing can defer it", () => {
    expect(themeScript).not.toMatch(/\bimport\b/);
    expect(themeScript).not.toMatch(/async|defer/);
    // The tag that loads it must not defer either: it has to run before the
    // module bundle and before first paint.
    const tag = html.match(/<script\b[^>]*boot-theme\.js[^>]*>/i)?.[0] ?? "";
    expect(tag).not.toMatch(/\b(defer|async)\b/);
    expect(tag).not.toContain('type="module"');
  });

  it("declares both colour schemes so native controls follow the class", () => {
    expect(html).toContain('<meta name="color-scheme" content="dark light"');
  });

  it("tells the browser chrome the same two colours", () => {
    expect(html).toContain(`<meta name="theme-color" content="${themeToken(":root {", "bg")}" />`);
    expect(html).toContain(
      `<meta name="theme-color" content="${themeToken("html.theme-light", "bg")}" media="(prefers-color-scheme: light)" />`,
    );
  });
});
