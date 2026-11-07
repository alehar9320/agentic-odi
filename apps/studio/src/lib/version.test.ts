import { describe, expect, it } from "vitest";

import { STUDIO_VERSION } from "./version";

describe("STUDIO_VERSION", () => {
  it("matches package.json and release manifest", async () => {
    const pkg = await import("../../package.json");
    const release = await import("../../../../.release-please-manifest.json");
    expect(STUDIO_VERSION).toBe(pkg.version ?? pkg.default?.version);
    expect(STUDIO_VERSION).toBe(release["."] ?? release.default?.["."]);
  });
});