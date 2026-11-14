import { describe, expect, it } from "vitest";

import { INITIAL_REGIONS, regionReducer, type RegionState } from "./regions";

/**
 * The navigation contract from #735, proved without a renderer:
 * one detail slot, and opening one closes nothing else.
 */
describe("region reducer", () => {
  it("opens a detail and keeps the drawer open beside it", () => {
    let state = regionReducer(INITIAL_REGIONS, { type: "open-drawer" });
    state = regionReducer(state, { type: "open-detail", panel: "landscape" });

    expect(state.detail).toEqual({ panel: "landscape" });
    // The drawer is a region, not an overlay: a detail never dismisses it.
    expect(state.drawerOpen).toBe(true);
  });

  it("keeps one detail slot, so two regions never show one subject", () => {
    let state = regionReducer(INITIAL_REGIONS, {
      type: "open-detail",
      panel: "landscape",
      subject: { kind: "outcome", id: "O-1" },
    });
    state = regionReducer(state, {
      type: "open-detail",
      panel: "evidence",
      subject: { kind: "evidence", id: "E-9" },
    });

    expect(state.detail).toEqual({ panel: "evidence", subject: { kind: "evidence", id: "E-9" } });
  });

  it("carries the subject a detail is about", () => {
    const state = regionReducer(INITIAL_REGIONS, {
      type: "open-detail",
      panel: "jobmap",
      subject: { kind: "job", id: "J-1" },
    });
    expect(state.detail?.subject).toEqual({ kind: "job", id: "J-1" });
  });

  it("closes the detail and leaves the drawer where it was", () => {
    let state = regionReducer(INITIAL_REGIONS, { type: "open-drawer" });
    state = regionReducer(state, { type: "open-detail", panel: "landscape" });
    state = regionReducer(state, { type: "close-detail" });

    expect(state.detail).toBeNull();
    expect(state.drawerOpen).toBe(true);
  });

  it("toggles the drawer without touching the detail", () => {
    let state = regionReducer(INITIAL_REGIONS, { type: "open-detail", panel: "landscape" });
    state = regionReducer(state, { type: "toggle-drawer" });
    expect(state.drawerOpen).toBe(true);
    expect(state.detail).toEqual({ panel: "landscape" });

    state = regionReducer(state, { type: "toggle-drawer" });
    expect(state.drawerOpen).toBe(false);
    expect(state.detail).toEqual({ panel: "landscape" });
  });

  it("returns the same state object when nothing changes", () => {
    const state: RegionState = INITIAL_REGIONS;
    expect(regionReducer(state, { type: "close-detail" })).toBe(state);
    expect(regionReducer(state, { type: "close-drawer" })).toBe(state);
  });
});
