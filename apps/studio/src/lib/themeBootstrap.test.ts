import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const BOOT_JS = resolve(__dirname, "../../public/boot-theme.js");
const THEME_TS = resolve(__dirname, "./theme.ts");
const SETTINGS_TSX = resolve(__dirname, "../state/settings/SettingsContext.tsx");
const TYPES_TS = resolve(__dirname, "../types.ts");

function read(path: string): string {
  return readFileSync(path, { encoding: "utf8" });
}

const boot = read(BOOT_JS);
const theme = read(THEME_TS);
const settings = read(SETTINGS_TSX);
const types = read(TYPES_TS);

describe("theme bootstrap / app parity", () => {
  it("storage key is the same in the bootstrap and the settings context", () => {
    expect(boot).toContain('"studio.settings"');
    expect(settings).toContain('SETTINGS_KEY = "studio.settings"');
  });

  it("media query is the same in the bootstrap and resolveTheme", () => {
    expect(boot).toContain('"(prefers-color-scheme: light)"');
    expect(theme).toContain('"(prefers-color-scheme: light)"');
  });

  it("fallback is dark in both", () => {
    expect(boot).toContain('"dark"');
    expect(theme).toContain('return "dark"');
  });

  it("accepted values match StudioTheme in both", () => {
    expect(types).toContain('export type StudioTheme = "light" | "dark";');
    expect(boot).toContain('stored.theme === "light" || stored.theme === "dark"');
    expect(theme).toContain('stored === "light" || stored === "dark"');
  });
});
