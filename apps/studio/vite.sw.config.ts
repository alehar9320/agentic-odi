import { createHash } from "node:crypto";
import { readdirSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vite";

const DIST = fileURLToPath(new URL("./dist", import.meta.url));

/** The same value the app build bakes in, so the two agree on the release date. */
const BUILD_DATE = new Date().toISOString().slice(0, 10);

/** The file kinds the shell needs offline. Anything else is not the shell. */
const PRECACHE_EXTENSIONS = new Set([
  ".html",
  ".js",
  ".css",
  ".png",
  ".svg",
  ".ico",
  ".webmanifest",
]);

/**
 * Every file under `dist/` as an origin-root URL, excluding the worker itself.
 *
 * The manifest is read from the app build's output, which has already run when
 * this build starts (`npm run build` chains them). Reading the real directory —
 * rather than naming files — keeps the precache list in step with the hashed
 * chunk names the app build emits.
 */
function collectPrecacheUrls(root: string, dir = root): string[] {
  const urls: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      urls.push(...collectPrecacheUrls(root, full));
      continue;
    }
    const dot = entry.name.lastIndexOf(".");
    const extension = dot === -1 ? "" : entry.name.slice(dot);
    if (!PRECACHE_EXTENSIONS.has(extension) || entry.name === "sw.js") {
      continue;
    }
    urls.push(`/${relative(root, full).split(sep).join("/")}`);
  }
  return urls.sort();
}

const PRECACHE = collectPrecacheUrls(DIST);

/**
 * The cache version.
 *
 * It hashes the precache list, so any new asset name moves it and `activate`
 * retires the previous cache. A date alone would keep two same-day builds on one
 * cache and serve yesterday's shell.
 */
const CACHE_VERSION = createHash("sha256")
  .update(`${BUILD_DATE}\n${PRECACHE.join("\n")}`)
  .digest("hex")
  .slice(0, 8);

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
    // Baked into the worker so its cache name moves with the release, and the
    // shell precache names the exact files the app build just emitted.
    __STUDIO_BUILD_DATE__: JSON.stringify(BUILD_DATE),
    __STUDIO_CACHE_VERSION__: JSON.stringify(CACHE_VERSION),
    __STUDIO_PRECACHE__: JSON.stringify(PRECACHE),
  },
});
