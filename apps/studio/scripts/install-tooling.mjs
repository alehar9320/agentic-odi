// Installs the optional test tooling declared in package.tooling.json (#752).
//
// A default `npm ci` no longer pulls Playwright, Chromatic, or the Tauri CLI,
// so the e2e, visual, and desktop paths install exactly what they need here.
// `--no-save` keeps package.json and package-lock.json untouched: the lock
// stays the single source of truth, and this only populates node_modules.
//
//   node scripts/install-tooling.mjs           install the tooling
//   node scripts/install-tooling.mjs --check   verify it is present, else fail
//
// The `--check` mode is what the test scripts call first, so a missing
// toolchain is a loud, named error instead of a silent skip.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const studioDir = join(dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(join(studioDir, "package.tooling.json"), "utf8"));
const names = Object.keys(manifest.devDependencies ?? {});

const missing = names.filter(
  (name) => !existsSync(join(studioDir, "node_modules", ...name.split("/"))),
);

if (process.argv.includes("--check")) {
  if (missing.length === 0) process.exit(0);
  console.error(
    `Optional test tooling is not installed (${missing.join(", ")}).\n` +
      "Install it with:  npm run tooling:install",
  );
  process.exit(1);
}

if (names.length === 0) {
  console.error("package.tooling.json declares no devDependencies; nothing to install.");
  process.exit(1);
}

const specs = Object.entries(manifest.devDependencies).map(([name, version]) => `${name}@${version}`);
const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const result = spawnSync(npm, ["install", "--no-save", "--no-audit", "--no-fund", ...specs], {
  cwd: studioDir,
  stdio: "inherit",
});

if (result.error) {
  console.error(`Could not run npm: ${result.error.message}`);
  process.exit(1);
}
if (result.status !== 0) {
  console.error(
    `Installing the optional test tooling failed (npm exited ${result.status}). ` +
      "Run `npm ci` first, then `npm run tooling:install`.",
  );
  process.exit(result.status ?? 1);
}
