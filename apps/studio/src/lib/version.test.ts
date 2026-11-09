/// <reference types="node" />
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { STUDIO_VERSION, versionLabel } from "./version";

const here = (relative: string): string =>
  readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

// The build version is the single source of truth: it is baked in from
// `apps/studio/package.json` and must match the release manifest, so a
// component can never carry a second literal that drifts.
describe("STUDIO_VERSION", () => {
  it("equals the version declared in apps/studio/package.json", () => {
    const pkg = JSON.parse(here("../../package.json")) as { version: string };
    expect(STUDIO_VERSION).toBe(pkg.version);
  });

  it("equals the version in the release-please manifest", () => {
    const manifest = JSON.parse(
      here("../../../../.release-please-manifest.json"),
    ) as Record<string, string>;
    expect(STUDIO_VERSION).toBe(manifest["."]);
  });
});

describe("versionLabel", () => {
  it("prefers a desktop updater version when it has one", () => {
    expect(versionLabel("0.11.0")).toEqual({ version: "0.11.0", source: "desktop" });
  });

  it("falls back to the build version outside the desktop shell", () => {
    expect(versionLabel(null)).toEqual({ version: STUDIO_VERSION, source: "build" });
    expect(versionLabel(undefined)).toEqual({ version: STUDIO_VERSION, source: "build" });
    expect(versionLabel("")).toEqual({ version: STUDIO_VERSION, source: "build" });
    expect(versionLabel("   ")).toEqual({ version: STUDIO_VERSION, source: "build" });
  });
});