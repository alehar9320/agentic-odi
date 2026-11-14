/**
 * #963: the desktop splash is a window and a page, neither of which vitest can
 * import — the behaviour lives in `tauri.conf.json`, the Rust shell, and a plain
 * HTML file. The promises are asserted against those files themselves, the way
 * `brandCopy.test.ts`, `offlinePage.test.ts`, and `windowState.test.ts` guard
 * their own surfaces.
 *
 * Vitest runs with the studio package as its working directory.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { PRODUCT_NAME } from "./brand";

const STUDIO = process.cwd();
const TAURI = join(STUDIO, "src-tauri");

const page = readFileSync(join(STUDIO, "public", "splashscreen.html"), "utf8");
const rust = readFileSync(join(TAURI, "src", "lib.rs"), "utf8");

interface WindowConfig {
  label: string;
  title?: string;
  url?: string;
  visible?: boolean;
  decorations?: boolean;
  resizable?: boolean;
  alwaysOnTop?: boolean;
  skipTaskbar?: boolean;
}

const conf = JSON.parse(readFileSync(join(TAURI, "tauri.conf.json"), "utf8")) as {
  app: { windows: WindowConfig[] };
};
const main = conf.app.windows.find((window) => window.label === "main")!;
const splash = conf.app.windows.find((window) => window.label === "splashscreen")!;

describe("the splash window", () => {
  it("declares both windows, main hidden and the splash shown", () => {
    expect(conf.app.windows).toHaveLength(2);
    expect(main).toBeDefined();
    expect(splash).toBeDefined();
    // The official Tauri pattern: main stays invisible until the frontend
    // reports in, so nothing flashes behind the splash.
    expect(main.visible).toBe(false);
    expect(splash.visible).toBe(true);
  });

  it("loads the splash page and wears the product name", () => {
    expect(splash.url).toBe("splashscreen.html");
    expect(main.title).toBe(PRODUCT_NAME);
    expect(splash.title).toBe(PRODUCT_NAME);
  });

  it("is a small, undecorated plate rather than a second app window", () => {
    expect(splash.resizable).toBe(false);
    expect(splash.decorations).toBe(false);
    expect(splash.alwaysOnTop).toBe(true);
    expect(splash.skipTaskbar).toBe(true);
  });
});

describe("the handover", () => {
  it("exposes the frontend's report as one command", () => {
    expect(rust).toMatch(/#\[tauri::command\]\s*\nfn set_complete\(/);
    expect(rust).toContain("generate_handler![set_complete]");
  });

  it("reveals main and closes the splash, once", () => {
    const reveal = rust.slice(rust.indexOf("fn reveal("), rust.indexOf("#[tauri::command]"));
    expect(reveal).toContain('get_webview_window("main")');
    expect(reveal).toContain("main.show()");
    expect(reveal).toContain("get_webview_window(SPLASH_WINDOW)");
    // The latch: the frontend, the timer, and the watchdog race here.
    expect(reveal).toContain("swap(true");
  });

  it("holds a short minimum display, so a fast boot cannot blink past", () => {
    expect(rust).toMatch(/SPLASH_MIN_VISIBLE: Duration = Duration::from_millis\(9\d\d\)/);
    expect(rust).toContain("SPLASH_MIN_VISIBLE.saturating_sub");
  });

  it("never strands the app on the splash when nothing reports", () => {
    // A watchdog, and a frontend timeout, so a lost message still opens a window.
    expect(rust).toMatch(/SPLASH_MAX_WAIT: Duration = Duration::from_secs\([1-9]\d*\)/);
    expect(rust).toContain("std::thread::sleep(SPLASH_MAX_WAIT)");
    const helper = readFileSync(join(STUDIO, "src", "lib", "splash.ts"), "utf8");
    expect(helper).toContain("SPLASH_ACK_TIMEOUT_MS");
  });

  it("offers an opt-out for very fast machines", () => {
    expect(rust).toContain("AGENTIC_ODI_SPLASH");
    expect(rust).toContain("SPLASH_SKIP_BELOW");
    expect(rust).toContain("fn splash_enabled()");
  });
});

describe("the splash page", () => {
  it("is branded with the mascot and the wordmark", () => {
    expect(page).toContain("odi-mascot");
    expect(page).toMatch(/alt="Odi the otter"/);
    expect(page).toContain(`<p class="splash__wordmark">${PRODUCT_NAME}</p>`);
  });

  it("is theme aware, resolved before first paint from the shell's own key", () => {
    expect(page).toContain("html.theme-light");
    expect(page).toMatch(/--bg: #0a0b0e/);
    expect(page).toMatch(/--bg: #f5f6f8/);
    expect(page).toContain("studio.settings");
  });

  it("asks the network for nothing but the mascot the shell already ships", () => {
    expect(page).not.toMatch(/@import/i);
    expect(page).not.toMatch(/@font-face/i);
    expect(page).not.toMatch(/https?:\/\//i);
    // The one request is the bundled, local mascot.
    const sources = page.match(/src="([^"]+)"/g) ?? [];
    expect(sources).toEqual(['src="/odi-mascot-256.png"']);
  });

  it("respects reduced motion and keeps the motion minimal", () => {
    expect(page).toContain("prefers-reduced-motion: reduce");
    const reduce = page.slice(page.indexOf("prefers-reduced-motion"));
    expect(reduce).toContain("animation: none");
    // Exactly two decorative animations, both retired under the media query.
    expect(page.match(/animation: splash-/g)).toHaveLength(2);
  });

  it("is announced without trapping the keyboard", () => {
    expect(page).toMatch(/<main class="splash" aria-label="/);
    expect(page).toMatch(/role="status"/);
    // No script beyond the synchronous theme resolution, and no focusable control.
    expect(page.match(/<script/g)).toHaveLength(1);
    expect(page).not.toMatch(/tabindex/i);
  });
});
