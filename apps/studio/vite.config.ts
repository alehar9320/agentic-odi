import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/**
 * The release version, read from the committed build-info source.
 *
 * `apps/cli/src/agentic_odi_cli/_build_info.py` is bumped by release-please and
 * pinned to `.release-please-manifest.json` by `tests/scripts/test_version_sync.py`,
 * so Settings can report the app version without inventing one. `apps/studio/package.json`
 * is bumped alongside it and is the fallback. `STUDIO_APP_VERSION` lets the
 * release workflow override it for a tagged build.
 */
function buildInfoVersion(): string {
  try {
    const source = readFileSync(
      fileURLToPath(new URL("../../apps/cli/src/agentic_odi_cli/_build_info.py", import.meta.url)),
      "utf8",
    );
    const match = /^VERSION\s*=\s*"([^"]+)"/m.exec(source);
    if (match) {
      return match[1];
    }
  } catch {
    // Fall through to the studio's own declared version.
  }
  try {
    const pkg = JSON.parse(
      readFileSync(fileURLToPath(new URL("./package.json", import.meta.url)), "utf8"),
    ) as { version?: string };
    return pkg.version ?? "0.0.0";
  } catch {
    return "0.0.0";
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // Copied components keep the import paths they shipped with
    // (`@/components/ui/…`, `@/lib/utils`) and stay inside the tree.
    alias: {
      "@": fileURLToPath(new URL("./src/vendor", import.meta.url)),
    },
  },
  clearScreen: false,
  // Settings → About reports which build is running. The version follows the
  // committed build-info source, the date is baked in at build time, and the
  // commit is the CI-provided sha ("dev" in a source checkout). Applies to
  // vitest transforms too.
  define: {
    __STUDIO_APP_VERSION__: JSON.stringify(process.env.STUDIO_APP_VERSION ?? buildInfoVersion()),
    __STUDIO_BUILD_DATE__: JSON.stringify(
      process.env.STUDIO_BUILD_DATE ?? new Date().toISOString().slice(0, 10),
    ),
    __STUDIO_BUILD_COMMIT__: JSON.stringify(
      process.env.STUDIO_BUILD_COMMIT ?? process.env.GITHUB_SHA ?? "dev",
    ),
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8100",
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    // Most tests never look at CSS; the print contract test reads a
    // stylesheet's source. Process CSS only when a test asks for it with a
    // query (?raw/?inline), so the rest of the suite keeps the faster path.
    css: { include: [/\.css(\?.*)?$/] },
    testTimeout: 10000,
    hookTimeout: 10000,
    // Visual tests need Chromium, so they run from vitest.visual.config.ts and
    // never from this jsdom suite (see docs/development.md).
    exclude: [...configDefaults.exclude, "**/*.visual.test.tsx"],
    // Vitest's default include is `**/*.{test,spec}.?(c|m)[jt]s?(x)`, which
    // would also collect the Playwright specs in `e2e/`. Scope it to the unit
    // tests so the two runners never overlap.
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
