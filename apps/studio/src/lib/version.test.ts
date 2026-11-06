import { describe, expect, it } from "vitest";

import { STUDIO_VERSION } from "./version";

import pkg from "../../package.json";
import release from "../../../../.release-please-manifest.json";

describe("STUDIO_VERSION", () => {
  it("equals the package version and the release manifest root", () => {
    expect(STUDIO_VERSION).toBe((pkg as { version: string }).version);
    expect(STUDIO_VERSION).toBe((release as { ".": string })["."]);
  });
});
