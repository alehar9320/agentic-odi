import { useCallback, useReducer } from "react";

import type { WorkspacePanelId } from "../types";

/**
 * The three regions and the one direction they move in (#735).
 *
 *   Drawer    = what you are working on.
 *   Mainstage = the work itself.
 *   Right     = one detail at a time, reachable only from a mainstage element
 *               that offers it. Deeper is right; backing out is left.
 *
 * This module is the single declaration of that contract, kept out of
 * `StudioContext.tsx` on purpose: #345 and #506 are splitting that provider, so
 * region state added to its body would be a merge conflict rather than a split.
 * Every later child reads this surface and none of them grows it.
 */

/** What a detail is about: a record the mainstage pointed at. */
export interface DetailSubject {
  kind: string;
  id: string;
}

/** The right region holds exactly one of these. */
export interface Detail {
  panel: WorkspacePanelId;
  subject?: DetailSubject;
}

export interface RegionState {
  detail: Detail | null;
  drawerOpen: boolean;
  collapsed: boolean;
}

export type RegionAction =
  | { type: "open-detail"; panel: WorkspacePanelId; subject?: DetailSubject }
  | { type: "close-detail" }
  | { type: "open-drawer" }
  | { type: "close-drawer" }
  | { type: "toggle-drawer" }
  | { type: "set-collapsed"; collapsed: boolean };

export const INITIAL_REGIONS: RegionState = {
  detail: null,
  drawerOpen: false,
  collapsed: false,
};

/**
 * Pure, so the contract is provable without a renderer.
 *
 * `open-detail` closes nothing else: the drawer is a region, not an overlay, so
 * opening a detail never dismisses the work list beside it. There is one detail
 * slot, so no state exists in which two regions show the same subject.
 */
export function regionReducer(state: RegionState, action: RegionAction): RegionState {
  switch (action.type) {
    case "open-detail":
      return { ...state, detail: { panel: action.panel, ...(action.subject ? { subject: action.subject } : {}) } };
    case "close-detail":
      return state.detail === null ? state : { ...state, detail: null };
    case "open-drawer":
      return state.drawerOpen ? state : { ...state, drawerOpen: true };
    case "close-drawer":
      return state.drawerOpen ? { ...state, drawerOpen: false } : state;
    case "toggle-drawer":
      return { ...state, drawerOpen: !state.drawerOpen };
    case "set-collapsed":
      return state.collapsed === action.collapsed ? state : { ...state, collapsed: action.collapsed };
    default:
      return state;
  }
}

/** The region surface `StudioContext` re-exports. */
export interface RegionSurface {
  detail: Detail | null;
  openDetail: (panel: WorkspacePanelId, subject?: DetailSubject) => void;
  closeDetail: () => void;
  drawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
  toggleDrawer: () => void;
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
}

export function useRegionState(): RegionSurface {
  const [state, dispatch] = useReducer(regionReducer, INITIAL_REGIONS);

  const openDetail = useCallback(
    (panel: WorkspacePanelId, subject?: DetailSubject) =>
      dispatch({ type: "open-detail", panel, ...(subject ? { subject } : {}) }),
    [],
  );
  const closeDetail = useCallback(() => dispatch({ type: "close-detail" }), []);
  const openDrawer = useCallback(() => dispatch({ type: "open-drawer" }), []);
  const closeDrawer = useCallback(() => dispatch({ type: "close-drawer" }), []);
  const toggleDrawer = useCallback(() => dispatch({ type: "toggle-drawer" }), []);
  const setCollapsed = useCallback(
    (collapsed: boolean) => dispatch({ type: "set-collapsed", collapsed }),
    [],
  );

  return {
    detail: state.detail,
    openDetail,
    closeDetail,
    drawerOpen: state.drawerOpen,
    openDrawer,
    closeDrawer,
    toggleDrawer,
    collapsed: state.collapsed,
    setCollapsed,
  };
}
