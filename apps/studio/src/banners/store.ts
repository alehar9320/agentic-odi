/**
 * The banner store, as pure functions.
 *
 * No React here: ordering, dedupe, and capping are the rules most likely to be
 * wrong and the cheapest to test, so they live where a test needs no DOM.
 *
 * A banner's `kind` is its identity. Raising a kind that is already up updates
 * it in place, which is what keeps a retry loop from painting ten copies of the
 * same warning.
 */

import { resolveSpec, severityWeight } from "./catalog";
import type { Banner, BannerKind, BannerSpec } from "./types";

export const DEFAULT_MAX_VISIBLE = 3;

export interface BannerState {
  banners: Banner[];
}

export const EMPTY_BANNER_STATE: BannerState = { banners: [] };

export function raiseBanner(state: BannerState, spec: BannerSpec, now = Date.now()): BannerState {
  const resolved = resolveSpec(spec);
  const banner: Banner = { ...resolved, id: spec.kind, raisedAt: now };
  const existing = state.banners.findIndex((entry) => entry.kind === spec.kind);
  if (existing === -1) {
    return { banners: [...state.banners, banner] };
  }
  const banners = state.banners.slice();
  banners[existing] = banner;
  return { banners };
}

export function resolveBanner(state: BannerState, kind: BannerKind): BannerState {
  return { banners: state.banners.filter((banner) => banner.kind !== kind) };
}

export function dismissBanner(state: BannerState, id: string): BannerState {
  return { banners: state.banners.filter((banner) => banner.id !== id) };
}

/**
 * The visible set, most severe first. Critical banners win the cap, so a burst
 * of success banners can never push a warning off-screen.
 */
export function selectBanners(
  state: BannerState,
  maxVisible = DEFAULT_MAX_VISIBLE,
): { visible: Banner[]; overflow: number } {
  const ordered = state.banners
    .slice()
    .sort(
      (a, b) => severityWeight(b.severity) - severityWeight(a.severity) || b.raisedAt - a.raisedAt,
    );
  const visible = ordered.slice(0, maxVisible);
  return { visible, overflow: Math.max(0, ordered.length - visible.length) };
}
