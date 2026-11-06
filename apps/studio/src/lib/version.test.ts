import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { STUDIO_VERSION } from "./version";

const pkg = JSON.parse(readFileSync("package.json", "utf8"));
const release = JSON.parse(readFileSync("../../.release-please-manifest.json", "utf8"));

describe("STUDIO_VERSION parity", () => {
  it("matches package.json version", () => {
    expect(STUDIO_VERSION).toBe(pkg.version);
  });

  it("matches release manifest version", () => {
    expect(STUDIO_VERSION).toBe(release["."]);
  });
});
