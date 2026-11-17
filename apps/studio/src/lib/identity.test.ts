import { describe, expect, it } from "vitest";

import { IDENTITY_ROLE_PLACEHOLDER, identityFor } from "./identity";

describe("identityFor", () => {
  it("uses the stored display name and its first letter", () => {
    expect(identityFor("Ada Lovelace")).toEqual({
      name: "Ada Lovelace",
      initial: "A",
      role: null,
    });
  });

  it("trims the name before it becomes the chip", () => {
    expect(identityFor("  Grace  ")).toMatchObject({ name: "Grace", initial: "G" });
  });

  it("falls back to You when Settings has no name", () => {
    expect(identityFor("   ")).toMatchObject({ name: "You", initial: "Y" });
  });

  it("labels the role gap instead of guessing one", () => {
    expect(identityFor("Ada").role).toBeNull();
    expect(IDENTITY_ROLE_PLACEHOLDER).toBe("Colleague — not set from your account");
  });
});
