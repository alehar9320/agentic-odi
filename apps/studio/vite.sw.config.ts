import { defineConfig } from "vite";

/**
 * A second, tiny build for the service worker.
 *
 * The main `vite build` clears `dist` and emits the app; this runs after it and
 * writes `dist/sw.js` next to the shell without emptying the directory. The
 * worker is one file at the origin root, so its scope is `/`.
 */
export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: false,
    lib: {
      entry: "src/sw.ts",
      formats: ["es"],
      fileName: () => "sw.js",
    },
  },
  define: {
    // Same value the app build bakes in, so the cache name moves with a release.
    __STUDIO_BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 10)),
  },
});
