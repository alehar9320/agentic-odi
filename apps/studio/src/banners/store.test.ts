import { describe, expect, it } from "vitest";

import {
  EMPTY_BANNER_STATE,
  dismissBanner,
  raiseBanner,
  resolveBanner,
  selectBanners,
} from "./store";

/** The five persistent top strips the cap and ordering rules are proved with.
 * Distinct `key`s are distinct banners even when they share a kind. */
const FIVE_TOP_STRIPS = [
  { kind: "write-rejected", key: "a" },
  { kind: "write-rejected", key: "b" },
  { kind: "offline" },
  { kind: "update-available" },
  { kind: "update-ready" },
] as const;

describe("raiseBanner", () => {
  it("adds a banner resolved from its kind", () => {
    const state = raiseBanner(EMPTY_BANNER_STATE, { kind: "write-rejected" });
    expect(state.banners).toHaveLength(1);
    expect(state.banners[0].severity).toBe("critical");
    expect(state.banners[0].id).toBe("write-rejected");
  });

  it("updates in place when the same persistent kind is raised twice", () => {
    let state = raiseBanner(EMPTY_BANNER_STATE, { kind: "write-rejected", body: "First." }, 100);
    state = raiseBanner(state, { kind: "write-rejected", body: "Second." }, 200);
    expect(state.banners).toHaveLength(1);
    expect(state.banners[0].body).toBe("Second.");
  });

  it("reappears when a dismissed kind is raised again", () => {
    let state = raiseBanner(EMPTY_BANNER_STATE, { kind: "write-rejected" }, 100);
    state = dismissBanner(state, "write-rejected");
    expect(state.banners).toHaveLength(0);
    state = raiseBanner(state, { kind: "write-rejected" }, 300);
    expect(state.banners).toHaveLength(1);
  });
});

describe("transient banners stack", () => {
  it("keeps both when two different messages of the same kind are raised", () => {
    let state = raiseBanner(EMPTY_BANNER_STATE, { kind: "success", body: "Added A." }, 100);
    state = raiseBanner(state, { kind: "success", body: "Added B." }, 200);
    expect(state.banners).toHaveLength(2);
    expect(state.banners.map((banner) => banner.body)).toEqual(["Added A.", "Added B."]);
  });

  it("gives each transient banner a distinct id", () => {
    let state = raiseBanner(EMPTY_BANNER_STATE, { kind: "success", body: "A." }, 100);
    state = raiseBanner(state, { kind: "success", body: "B." }, 200);
    expect(new Set(state.banners.map((banner) => banner.id)).size).toBe(2);
  });
});

describe("resolveBanner", () => {
  it("removes the banner for a kind", () => {
    let state = raiseBanner(EMPTY_BANNER_STATE, { kind: "offline" });
    state = resolveBanner(state, "offline");
    expect(state.banners).toHaveLength(0);
  });
});

describe("selectBanners", () => {
  it("orders by severity, critical first", () => {
    let state = raiseBanner(EMPTY_BANNER_STATE, { kind: "success" }, 1);
    state = raiseBanner(state, { kind: "write-rejected" }, 2);
    const { visible } = selectBanners(state);
    expect(visible[0].severity).toBe("critical");
  });

  it("caps a dock's visible set and counts the rest as overflow", () => {
    let state = EMPTY_BANNER_STATE;
    for (const spec of FIVE_TOP_STRIPS) {
      state = raiseBanner(state, { kind: spec.kind, ...("key" in spec ? { key: spec.key } : {}) });
    }
    const { visible, overflow } = selectBanners(state, 3);
    expect(visible).toHaveLength(3);
    expect(overflow).toBe(2);
  });

  it("caps each dock on its own, so top strips never hide corner notices", () => {
    let state = EMPTY_BANNER_STATE;
    for (const spec of FIVE_TOP_STRIPS) {
      state = raiseBanner(state, { kind: spec.kind, ...("key" in spec ? { key: spec.key } : {}) });
    }
    state = raiseBanner(state, { kind: "success", body: "Saved." });
    const { visible } = selectBanners(state, 3);
    expect(visible.some((banner) => banner.dock === "corner")).toBe(true);
    expect(visible.filter((banner) => banner.dock === "top")).toHaveLength(3);
  });

  it("keeps the critical banners visible when a success banner would displace them", () => {
    let state = EMPTY_BANNER_STATE;
    for (const spec of FIVE_TOP_STRIPS) {
      state = raiseBanner(state, { kind: spec.kind, ...("key" in spec ? { key: spec.key } : {}) });
    }
    const { visible, overflow } = selectBanners(state, 3);
    const kinds = visible.map((banner) => banner.kind);
    expect(kinds).toContain("write-rejected");
    expect(kinds).not.toContain("update-ready");
    expect(overflow).toBe(2);
  });
});
