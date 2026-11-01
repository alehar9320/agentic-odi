import { describe, expect, it } from "vitest";

import { BANNER_CATALOG, resolveSpec, severityWeight } from "./catalog";
import type { BannerKind } from "./types";

const ALL_KINDS: BannerKind[] = [
  "sidecar-down",
  "model-offline",
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

  it("treats the sidecar being down as a critical, persistent, top strip", () => {
    const entry = BANNER_CATALOG["sidecar-down"];
    expect(entry.severity).toBe("critical");
    expect(entry.life).toBe("persistent");
    expect(entry.dock).toBe("top");
    expect(entry.dismissible).toBe(true);
  });

  it("treats a missing model as a warning strip that cannot be dismissed away", () => {
    const entry = BANNER_CATALOG["model-offline"];
    expect(entry.severity).toBe("warning");
    expect(entry.life).toBe("persistent");
    expect(entry.dismissible).toBe(false);
  });

  /**
   * A banner is raised in front of a person who may be standing in a hosted
   * studio with no sidecar at all, so naming a repository names something the
   * browser cannot keep. What they capture *is* saved — in the repository when
   * there is one, in the browser when there isn't — which is why the copy
   * promises a saving and not a destination. (#326 is the work that names the
   * store instead of leaving it implied.)
   */
  it("promises no repository a browser-only studio does not have", () => {
    for (const kind of ["model-offline", "sidecar-down"] as const) {
      expect(BANNER_CATALOG[kind].body, kind).not.toMatch(/repository|\bODI\b/i);
    }
  });

  it("says the assistant still answers from the board when no model is reachable", () => {
    expect(BANNER_CATALOG["model-offline"].body).toMatch(/answers from your board/i);
  });

  it("keeps the toast kinds transient and in the corner", () => {
    for (const kind of ["info", "success", "error"] as const) {
      expect(BANNER_CATALOG[kind].life).toBe("transient");
      expect(BANNER_CATALOG[kind].dock).toBe("corner");
    }
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
    const resolved = resolveSpec({ kind: "sidecar-down" });
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
