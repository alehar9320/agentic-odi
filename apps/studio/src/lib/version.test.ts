/// <reference types="node" />
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { STUDIO_VERSION } from "./version";

const here = (relative: string): string =>
  readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

describe("version parity", () => {
  it("STUDIO_VERSION matches package.json and release manifest", () => {
    const pkg = JSON.parse(here("../../package.json"));
    const release = JSON.parse(here("../../../../.release-please-manifest.json"));
    expect(STUDIO_VERSION).toBe(pkg.version);
    expect(STUDIO_VERSION).toBe(release["."]);
  });
});
