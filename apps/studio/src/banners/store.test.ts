import { describe, expect, it } from "vitest";

import {
  EMPTY_BANNER_STATE,
  dismissBanner,
  raiseBanner,
  resolveBanner,
  selectBanners,
} from "./store";

describe("raiseBanner", () => {
  it("adds a banner resolved from its kind", () => {
    const state = raiseBanner(EMPTY_BANNER_STATE, { kind: "sidecar-down" });
    expect(state.banners).toHaveLength(1);
    expect(state.banners[0].severity).toBe("critical");
    expect(state.banners[0].id).toBe("sidecar-down");
  });

  it("updates in place when the same kind is raised twice", () => {
    let state = raiseBanner(EMPTY_BANNER_STATE, { kind: "info", body: "First." }, 100);
    state = raiseBanner(state, { kind: "info", body: "Second." }, 200);
    expect(state.banners).toHaveLength(1);
    expect(state.banners[0].body).toBe("Second.");
  });

  it("reappears when a dismissed kind is raised again", () => {
    let state = raiseBanner(EMPTY_BANNER_STATE, { kind: "info" }, 100);
    state = dismissBanner(state, "info");
    expect(state.banners).toHaveLength(0);
    state = raiseBanner(state, { kind: "info" }, 300);
    expect(state.banners).toHaveLength(1);
  });
});

describe("resolveBanner", () => {
  it("removes the banner for a kind", () => {
    let state = raiseBanner(EMPTY_BANNER_STATE, { kind: "sidecar-down" });
    state = resolveBanner(state, "sidecar-down");
    expect(state.banners).toHaveLength(0);
  });
});

describe("selectBanners", () => {
  it("orders by severity, critical first", () => {
    let state = raiseBanner(EMPTY_BANNER_STATE, { kind: "success" }, 1);
    state = raiseBanner(state, { kind: "sidecar-down" }, 2);
    const { visible } = selectBanners(state);
    expect(visible[0].severity).toBe("critical");
  });

  it("caps the visible set and counts the rest as overflow", () => {
    let state = EMPTY_BANNER_STATE;
    for (const kind of ["sidecar-down", "model-offline", "update-available", "info", "success"] as const) {
      state = raiseBanner(state, { kind });
    }
    const { visible, overflow } = selectBanners(state, 3);
    expect(visible).toHaveLength(3);
    expect(overflow).toBe(2);
  });

  it("keeps the critical banners visible when a success banner would displace them", () => {
    let state = EMPTY_BANNER_STATE;
    for (const kind of [
      "update-ready",
      "update-available",
      "model-offline",
      "sidecar-down",
      "write-rejected",
    ] as const) {
      state = raiseBanner(state, { kind });
    }
    const { visible, overflow } = selectBanners(state, 3);
    const kinds = visible.map((banner) => banner.kind);
    expect(kinds).toContain("sidecar-down");
    expect(kinds).toContain("write-rejected");
    expect(kinds).not.toContain("update-ready");
    expect(overflow).toBe(2);
  });
});
