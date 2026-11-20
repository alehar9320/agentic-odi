import { describe, expect, it } from "vitest";

import themeTs from "./theme.ts?raw";
import bootThemeJs from "../../public/boot-theme.js?raw";
import typesTs from "../types.ts?raw";
import settingsContextTsx from "../state/settings/SettingsContext.tsx?raw";

function extractMediaQueryThemeTs(source: string): string | null {
  const match = source.match(/THEME_MEDIA_QUERY\s*=\s*["']([^"']+)["']/);
  return match ? match[1] : null;
}

function extractMediaQueryBootTheme(source: string): string | null {
  const match = source.match(/matchMedia\(["']([^"']+)["']\)/);
  return match ? match[1] : null;
}

function extractFallbackThemeTs(source: string): string | null {
  const match = source.match(/THEME_FALLBACK\s*:\s*StudioTheme\s*=\s*["']([^"']+)["']/);
  return match ? match[1] : null;
}

function extractFallbackBootTheme(source: string): string | null {
  const match = source.match(/theme\s*=\s*light\s*\?\s*["']light["']\s*:\s*["']dark["']/);
  return match ? "dark" : null;
}

function extractStorageKeyBootTheme(source: string): string | null {
  const match = source.match(/localStorage\.getItem\(["']([^"']+)["']\)/);
  return match ? match[1] : null;
}

function extractStorageKeySettingsContext(source: string): string | null {
  const match = source.match(/SETTINGS_KEY\s*=\s*["']([^"']+)["']/);
  return match ? match[1] : null;
}

function extractStudioThemeUnion(source: string): string | null {
  const match = source.match(/export\s+type\s+StudioTheme\s*=\s*([^;]+);/);
  return match ? match[1].trim() : null;
}

describe("theme bootstrap parity", () => {
  it("storage key in boot-theme.js matches the key SettingsContext.tsx exports", () => {
    const bootKey = extractStorageKeyBootTheme(bootThemeJs);
    const settingsKey = extractStorageKeySettingsContext(settingsContextTsx);
    expect(bootKey).toBe("studio.settings");
    expect(settingsKey).toBe("studio.settings");
    expect(bootKey).toBe(settingsKey);
  });

  it("media query in theme.ts matches the media query in boot-theme.js", () => {
    const tsQuery = extractMediaQueryThemeTs(themeTs);
    const jsQuery = extractMediaQueryBootTheme(bootThemeJs);
    expect(tsQuery).toBe("(prefers-color-scheme: light)");
    expect(jsQuery).toBe("(prefers-color-scheme: light)");
    expect(tsQuery).toBe(jsQuery);
  });

  it("fallback in theme.ts matches the fallback in boot-theme.js", () => {
    const tsFallback = extractFallbackThemeTs(themeTs);
    const jsFallback = extractFallbackBootTheme(bootThemeJs);
    expect(tsFallback).toBe("dark");
    expect(jsFallback).toBe("dark");
    expect(tsFallback).toBe(jsFallback);
  });

  it("accepted values in StudioTheme union match the values used in theme.ts and boot-theme.js", () => {
    const studioTheme = extractStudioThemeUnion(typesTs);
    expect(studioTheme).toBe('"light" | "dark"');
    expect(themeTs).toContain('"light"');
    expect(themeTs).toContain('"dark"');
    expect(bootThemeJs).toContain('"light"');
    expect(bootThemeJs).toContain('"dark"');
  });
});