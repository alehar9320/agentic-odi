import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * #962: the desktop app opens focused, not sprawling, and remembers the size
 * and position the person chose.
 *
 * The behaviour lives in two files vitest cannot import — `tauri.conf.json` and
 * the Rust shell — so the promises are asserted against the files themselves,
 * the way `brandCopy.test.ts` and `offlinePage.test.ts` guard their surfaces.
 *
 * Vitest runs with the studio package as its working directory.
 */
const STUDIO = process.cwd();
const TAURI = join(STUDIO, "src-tauri");

const conf = JSON.parse(readFileSync(join(TAURI, "tauri.conf.json"), "utf8")) as {
  app: {
    windows: {
      label: string;
      width: number;
      height: number;
      minWidth: number;
      minHeight: number;
      resizable: boolean;
    }[];
  };
};

const main = conf.app.windows.find((window) => window.label === "main")!;
const rust = readFileSync(join(TAURI, "src", "lib.rs"), "utf8");
const cargo = readFileSync(join(TAURI, "Cargo.toml"), "utf8");

describe("desktop window defaults", () => {
  it("opens smaller than a full desktop, so the first frame is focused", () => {
    expect(main.width).toBeGreaterThanOrEqual(1000);
    expect(main.width).toBeLessThanOrEqual(1200);
    expect(main.height).toBeGreaterThanOrEqual(700);
    expect(main.height).toBeLessThanOrEqual(800);
  });

  it("keeps a usable floor so the composer and canvas never break", () => {
    expect(main.minWidth).toBeGreaterThanOrEqual(900);
    expect(main.minHeight).toBeGreaterThanOrEqual(600);
    expect(main.minWidth).toBeLessThan(main.width);
    expect(main.minHeight).toBeLessThan(main.height);
  });

  it("stays resizable, so the person can grow it", () => {
    expect(main.resizable).toBe(true);
  });
});

describe("window state across sessions", () => {
  it("declares the window-state plugin once, in Cargo.toml and the shell", () => {
    expect(cargo).toMatch(/^tauri-plugin-window-state = "2"$/m);
    expect(rust).toContain("tauri_plugin_window_state::Builder::default()");
  });

  it("restores size, position, and maximized — never decorations or visibility", () => {
    const flags = rust.slice(rust.indexOf("with_state_flags"));
    expect(flags).toContain("StateFlags::SIZE");
    expect(flags).toContain("StateFlags::POSITION");
    expect(flags).toContain("StateFlags::MAXIMIZED");
    // A stale `visible: false` would open a window nobody can see.
    expect(flags).not.toContain("StateFlags::VISIBLE");
    expect(flags).not.toContain("StateFlags::DECORATIONS");
  });
});
