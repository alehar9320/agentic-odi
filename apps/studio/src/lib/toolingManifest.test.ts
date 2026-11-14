import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * #752: Playwright, Chromatic, and the Tauri CLI are optional tooling. They
 * live in `package.tooling.json` and are installed by `npm run tooling:install`
 * rather than by the default `npm ci`, so a clone, a lint-only job, and a
 * restricted agent sandbox never download a browser they will not use.
 *
 * Vitest runs with the studio package as its working directory.
 */
const read = (path: string): string => readFileSync(join(process.cwd(), path), "utf8");

const pkg = JSON.parse(read("package.json")) as {
  scripts: Record<string, string>;
  dependencies: Record<string, string>;
  devDependencies: Record<string, string>;
};
const tooling = JSON.parse(read("package.tooling.json")) as {
  devDependencies: Record<string, string>;
};

const TOOLING_PACKAGES = Object.keys(tooling.devDependencies);
const TOOLING_SCRIPTS = ["test:e2e", "test:e2e:ui", "test:visual", "chromatic", "tauri"];

describe("optional test tooling (#752)", () => {
  it("declares the seven tooling packages that left the default install", () => {
    expect(TOOLING_PACKAGES.sort()).toEqual(
      [
        "@chromatic-com/vitest",
        "@playwright/test",
        "@tauri-apps/cli",
        "@vitest/browser-playwright",
        "chromatic",
        "playwright",
        "vitest-browser-react",
      ].sort(),
    );
  });

  it("keeps the tooling out of the default install path", () => {
    const defaultInstall = { ...pkg.dependencies, ...pkg.devDependencies };
    for (const name of TOOLING_PACKAGES) {
      expect(defaultInstall, `${name} must not install by default`).not.toHaveProperty(name);
    }
  });

  it("pins the tooling to exact versions so the tree matches the lock", () => {
    for (const version of Object.values(tooling.devDependencies)) {
      expect(version).toMatch(/^\d+\.\d+\.\d+$/);
    }
  });

  it("guards every tooling-backed script with the presence check", () => {
    for (const script of TOOLING_SCRIPTS) {
      expect(pkg.scripts[script], script).toContain("install-tooling.mjs --check");
    }
  });
});
