import { describe, expect, it } from "vitest";

import { BANNER_CATALOG, resolveSpec, severityWeight } from "./catalog";
import type { BannerKind } from "./types";

const ALL_KINDS: BannerKind[] = [
  "offline",
  "app-update-ready",
  "update-available",
  "update-ready",
  "write-rejected",
  "info",
  "success",
  "error",
];

describe("BANNER_CATALOG", () => {
  it("defines every kind", () => {
    for (const kind of ALL_KINDS) {
      expect(BANNER_CATALOG[kind], `missing catalog entry for ${kind}`).toBeDefined();
    }
  });

  it("gives every entry a severity, a life, and a dock", () => {
    for (const [kind, entry] of Object.entries(BANNER_CATALOG)) {
      expect(entry.severity, kind).toMatch(/^(info|success|warning|critical)$/);
      expect(entry.life, kind).toMatch(/^(persistent|transient)$/);
      expect(entry.dock, kind).toMatch(/^(top|corner)$/);
    }
  });

  it("names what still works when the browser is offline, without claiming sync", () => {
    const entry = BANNER_CATALOG["offline"];
    expect(entry.severity).toBe("info");
    expect(entry.life).toBe("persistent");
    expect(entry.dock).toBe("top");
    // A persistent banner with no key would dedupe by kind only; the copy has to
    // name the device-local work and must not promise a sync that #306 owns.
    expect(`${entry.title} ${entry.body}`).toMatch(/offline/i);
    expect(`${entry.title} ${entry.body}`).toMatch(/device|here/i);
    expect(`${entry.title} ${entry.body}`).not.toMatch(/sync/i);
  });

  it("keeps the toast kinds transient and in the corner", () => {
    for (const kind of ["info", "success", "error"] as const) {
      expect(BANNER_CATALOG[kind].life).toBe("transient");
      expect(BANNER_CATALOG[kind].dock).toBe("corner");
    }
  });

  it("offers a reload, never a forced one, when a new build is staged", () => {
    const entry = BANNER_CATALOG["app-update-ready"];
    expect(entry.severity).toBe("info");
    expect(entry.life).toBe("persistent");
    expect(entry.dock).toBe("top");
    // The copy names the version and the action is an explicit reload, so the
    // update never swaps code on its own.
    expect(`${entry.title} ${entry.body}`).toMatch(/new version/i);
    expect(entry.actions?.[0]).toMatchObject({
      label: "Reload for the new version",
      action: "reload-app",
    });
  });
});

describe("severityWeight", () => {
  it("orders critical above warning above info above success", () => {
    expect(severityWeight("critical")).toBeGreaterThan(severityWeight("warning"));
    expect(severityWeight("warning")).toBeGreaterThan(severityWeight("info"));
    expect(severityWeight("info")).toBeGreaterThan(severityWeight("success"));
  });
});

describe("resolveSpec", () => {
  it("fills the defaults from the kind", () => {
    const resolved = resolveSpec({ kind: "write-rejected" });
    expect(resolved.severity).toBe("critical");
    expect(resolved.life).toBe("persistent");
    expect(resolved.dock).toBe("top");
  });

  it("lets a caller override severity and copy", () => {
    const resolved = resolveSpec({ kind: "info", severity: "warning", body: "Careful." });
    expect(resolved.severity).toBe("warning");
    expect(resolved.body).toBe("Careful.");
  });
});
