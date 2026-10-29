import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  // Settings → About reports which build is running; the release workflow's
  // date is baked in at build time. Applies to vitest transforms too.
  define: {
    __STUDIO_BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 10)),
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
    // Visual tests need Chromium, so they run from vitest.visual.config.ts and
    // never from this jsdom suite (see docs/development.md).
    exclude: [...configDefaults.exclude, "**/*.visual.test.tsx"],
    // Vitest's default include is `**/*.{test,spec}.?(c|m)[jt]s?(x)`, which
    // would also collect the Playwright specs in `e2e/`. Scope it to the unit
    // tests so the two runners never overlap.
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
