import { describe, expect, it } from "vitest";

import { formatShareExpiry, isShareExpired, sharedTokenFromPath } from "./share";

const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;
const NOW = Date.parse("2026-11-03T12:00:00+00:00");

describe("sharedTokenFromPath", () => {
  it("reads the token from a /shared/<token> path", () => {
    expect(sharedTokenFromPath("/shared/odi_sh_abc123")).toBe("odi_sh_abc123");
  });

  it("accepts a trailing slash but not a deeper path", () => {
    expect(sharedTokenFromPath("/shared/odi_sh_abc123/")).toBe("odi_sh_abc123");
    expect(sharedTokenFromPath("/shared/odi_sh_abc123/edit")).toBeNull();
  });

  it("returns null for every other route", () => {
    expect(sharedTokenFromPath("/")).toBeNull();
    expect(sharedTokenFromPath("/shared")).toBeNull();
    expect(sharedTokenFromPath("/shared/")).toBeNull();
    expect(sharedTokenFromPath("/canvas/shared/x")).toBeNull();
  });

  // A token with a broken percent escape must not crash the boot; it is simply
  // not a token this build can read.
  it("returns null for a malformed escape instead of throwing", () => {
    expect(sharedTokenFromPath("/shared/%E0%A4%A")).toBeNull();
  });
});

describe("isShareExpired", () => {
  it("is true once the expiry has passed", () => {
    expect(isShareExpired(new Date(NOW - 1).toISOString(), NOW)).toBe(true);
  });

  it("is false while the link is still live", () => {
    expect(isShareExpired(new Date(NOW + DAY).toISOString(), NOW)).toBe(false);
  });

  // A timestamp that will not parse must never be treated as "expired", which
  // would hide a live artifact behind a parse bug.
  it("is false for a timestamp that will not parse", () => {
    expect(isShareExpired("not a date", NOW)).toBe(false);
  });
});

describe("formatShareExpiry", () => {
  it("counts the whole days left", () => {
    expect(formatShareExpiry(new Date(NOW + 3 * DAY).toISOString(), NOW)).toBe(
      "expires in 3 days",
    );
  });

  it("uses the singular for one day", () => {
    expect(formatShareExpiry(new Date(NOW + DAY).toISOString(), NOW)).toBe("expires in 1 day");
  });

  it("says under a minute when less than a minute is left", () => {
    expect(formatShareExpiry(new Date(NOW + 30 * 1000).toISOString(), NOW)).toBe(
      "expires in under a minute",
    );
  });

  it("counts minutes under an hour", () => {
    expect(formatShareExpiry(new Date(NOW + 5 * 60 * 1000).toISOString(), NOW)).toBe(
      "expires in 5 minutes",
    );
  });

  it("uses the singular for one minute", () => {
    expect(formatShareExpiry(new Date(NOW + 60 * 1000).toISOString(), NOW)).toBe(
      "expires in 1 minute",
    );
  });

  it("counts minutes up to fifty-nine", () => {
    expect(formatShareExpiry(new Date(NOW + 59 * 60 * 1000).toISOString(), NOW)).toBe(
      "expires in 59 minutes",
    );
  });

  it("counts hours under a day", () => {
    expect(formatShareExpiry(new Date(NOW + 5 * HOUR).toISOString(), NOW)).toBe(
      "expires in 5 hours",
    );
  });

  it("uses the singular for one hour", () => {
    expect(formatShareExpiry(new Date(NOW + 61 * 60 * 1000).toISOString(), NOW)).toBe(
      "expires in 1 hour",
    );
  });

  it("counts hours up to twenty-three", () => {
    expect(formatShareExpiry(new Date(NOW + 23 * HOUR).toISOString(), NOW)).toBe(
      "expires in 23 hours",
    );
  });

  it("never says today for a sub-day link", () => {
    expect(formatShareExpiry(new Date(NOW + 2 * HOUR).toISOString(), NOW)).not.toBe(
      "expires today",
    );
  });

  it("returns null once the link has expired", () => {
    expect(formatShareExpiry(new Date(NOW - HOUR).toISOString(), NOW)).toBeNull();
  });

  it("returns null when the timestamp will not parse", () => {
    expect(formatShareExpiry("not a date", NOW)).toBeNull();
  });
});
