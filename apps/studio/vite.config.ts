import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";

import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The build version is the single source of truth: read from package.json here
// and baked in as a define so no component can carry a second literal that
// drifts from the release manifest.
const studioPackage = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf8"),
) as { version: string };

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
  build: {
    // Emit `dist/.vite/manifest.json` so the budget script measures the entry
    // chunk by role rather than by a hashed file name (#529).
    manifest: true,
    // The entry chunk is the cold-start budget (#529). Split the heavy vendor
    // libraries out of it so the shell and the current view are not shipped
    // behind the assistant runtime, the markdown renderer, or the Tauri API.
    // `scripts/check_bundle_budget.mjs` ratchets the recorded entry size.
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            // The conversation runtime and its markdown renderer.
            {
              name: "assistant",
              test: /[\\/]node_modules[\\/](@assistant-ui|@radix-ui|remark|rehype|unified|micromark|mdast-util|hast-util|unist-util)[\\/]/,
            },
            // The desktop shell's API and updater.
            { name: "tauri", test: /[\\/]node_modules[\\/]@tauri-apps[\\/]/ },
            // Everything else that came from node_modules.
            { name: "vendor", test: /[\\/]node_modules[\\/]/ },
          ],
        },
      },
    },
    // The entry chunk is bounded by the budget script, not this warning.
    chunkSizeWarningLimit: 700,
  },
  // Settings → About reports which build is running; the release workflow's
  // date is baked in at build time. Applies to vitest transforms too.
  define: {
    __STUDIO_BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 10)),
    __STUDIO_VERSION__: JSON.stringify(studioPackage.version),
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
