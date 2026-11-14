#!/usr/bin/env node
/**
 * The cold-start bundle budget (#529).
 *
 * The first screen must not wait on everything the app can do. `vite.config.ts`
 * splits the assistant runtime, the markdown renderer, and the Tauri API out of
 * the entry chunk; this script measures what is left and fails when it grows
 * past the recorded baseline plus a tolerance.
 *
 * The numbers are read from the build manifest, not from the file names, so a
 * content hash change is not a regression. The baseline is recorded next to the
 * script in `scripts/bundle-budget.json`; a deliberate increase is a one-line
 * edit to that file, made in the same pull request that earned it.
 *
 * Usage:
 *   node scripts/check_bundle_budget.mjs            # check the built dist
 *   node scripts/check_bundle_budget.mjs --update   # re-record the baseline
 *
 * Options (the defaults are the repository layout):
 *   --manifest <path>   the Vite build manifest (default: apps/studio/dist/.vite/manifest.json)
 *   --baseline <path>   where the recorded baseline lives (default: scripts/bundle-budget.json)
 *   --tolerance <n>     allowed growth as a fraction (default: 0.2)
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(HERE, "..");

function argValue(flag, fallback) {
  const index = process.argv.indexOf(flag);
  return index !== -1 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const MANIFEST = argValue("--manifest", join(REPO_ROOT, "apps/studio/dist/.vite/manifest.json"));
const BASELINE_FILE = argValue("--baseline", join(HERE, "bundle-budget.json"));
const TOLERANCE = Number(argValue("--tolerance", "0.2"));
// Asset paths in the manifest are relative to the build output root, which is
// the directory holding `.vite/`.
const DIST_ROOT = join(dirname(MANIFEST), "..");

function fail(message) {
  console.error(message);
  process.exit(1);
}

function sizeOf(relativeFile) {
  const path = join(DIST_ROOT, relativeFile);
  if (!existsSync(path)) {
    fail(`Manifest names ${relativeFile}, which is not on disk.`);
  }
  return readFileSync(path).byteLength;
}

if (!existsSync(MANIFEST)) {
  fail(
    `No build manifest at ${MANIFEST}. Build the Studio first: ` +
      `npm --prefix apps/studio run build`,
  );
}

const manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));

// The entry chunk is what a cold load must download before the shell can run.
// Vite records it as the manifest entry whose `isEntry` is true.
const entries = Object.entries(manifest).filter(([, chunk]) => chunk.isEntry);
if (entries.length !== 1) {
  fail(
    `Expected exactly one entry chunk in the manifest, found ${entries.length}. ` +
      `The cold-start budget measures a single entry; name the extras explicitly.`,
  );
}

const [, entry] = entries[0];
const entryBytes = sizeOf(entry.file);

// Every chunk a cold load pulls before the first screen: the entry plus its
// static imports. Dynamic imports are the panels that open later and are out of
// scope for this budget.
const coldChunks = new Set([entry.file]);
for (const imported of entry.imports ?? []) {
  const chunk = manifest[imported];
  if (chunk && chunk.file) {
    coldChunks.add(chunk.file);
  }
}
let coldBytes = 0;
for (const file of coldChunks) {
  coldBytes += sizeOf(file);
}

const measured = {
  entryBytes,
  entryKb: round(entryBytes / 1024),
  coldBytes,
  coldKb: round(coldBytes / 1024),
  entryFile: entry.file,
  coldChunks: [...coldChunks].sort(),
};

if (process.argv.includes("--update")) {
  writeFileSync(BASELINE_FILE, `${JSON.stringify(measured, null, 2)}\n`);
  console.log(`Recorded the bundle baseline in ${BASELINE_FILE}:`);
  print(measured);
  process.exit(0);
}

if (!existsSync(BASELINE_FILE)) {
  fail(
    `No recorded baseline at ${BASELINE_FILE}. Run ` +
      `\`node scripts/check_bundle_budget.mjs --update\` and commit the result.`,
  );
}

const baseline = JSON.parse(readFileSync(BASELINE_FILE, "utf8"));
const ceiling = Math.floor(baseline.entryBytes * (1 + TOLERANCE));

console.log("Cold-start bundle budget (#529)");
print(measured);
console.log(`  baseline entry: ${baseline.entryKb} kB`);
console.log(`  ceiling:        ${round(ceiling / 1024)} kB (+${Math.round(TOLERANCE * 100)}%)`);

if (entryBytes > ceiling) {
  fail(
    `\nThe entry chunk is ${measured.entryKb} kB, over the ${round(ceiling / 1024)} kB ` +
      `ceiling. Move the new weight behind a dynamic import, or record the ` +
      `increase deliberately with \`--update\` and say why in the pull request.`,
  );
}

console.log(`\nOK: the entry chunk is within budget.`);
process.exit(0);

function print(measured) {
  console.log(`  entry:  ${measured.entryKb} kB (${measured.entryFile})`);
  console.log(`  cold:   ${measured.coldKb} kB across ${measured.coldChunks.length} chunks`);
}

function round(value) {
  return Math.round(value * 10) / 10;
}
