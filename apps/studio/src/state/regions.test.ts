import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { MOBILE_QUERY } from "../lib/useMediaQuery";
import {
  DRAWER_STORAGE_KEY,
  INITIAL_REGIONS,
  initialDrawerOpen,
  readDrawerPreference,
  regionReducer,
  useRegionState,
  writeDrawerPreference,
  type RegionState,
} from "./regions";

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

const originalMatchMedia = window.matchMedia;

function setViewport(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches: query === MOBILE_QUERY ? matches : false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

describe("drawer persistence (#736)", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: originalMatchMedia,
    });
    window.localStorage.clear();
  });

  it("opens on a desk and stays closed where it would be a sheet", () => {
    setViewport(false);
    expect(initialDrawerOpen()).toBe(true);

    setViewport(true);
    expect(initialDrawerOpen()).toBe(false);
  });

  it("lets a stored choice beat the viewport", () => {
    setViewport(true);
    writeDrawerPreference(true);
    expect(initialDrawerOpen()).toBe(true);

    setViewport(false);
    writeDrawerPreference(false);
    expect(initialDrawerOpen()).toBe(false);
  });

  it("ignores an unknown stored value", () => {
    window.localStorage.setItem(DRAWER_STORAGE_KEY, "maybe");
    expect(readDrawerPreference()).toBeNull();
  });

  it("persists the first collapse and restores it on the next mount", () => {
    setViewport(false);
    const first = renderHook(() => useRegionState());
    expect(first.result.current.drawerOpen).toBe(true);

    act(() => first.result.current.toggleDrawer());

    expect(window.localStorage.getItem(DRAWER_STORAGE_KEY)).toBe("closed");
    const second = renderHook(() => useRegionState());
    expect(second.result.current.drawerOpen).toBe(false);
  });
});
