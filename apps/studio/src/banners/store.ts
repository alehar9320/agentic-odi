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

let transientCounter = 0;

function transientId(kind: BannerKind, now: number): string {
  transientCounter += 1;
  return `${kind}-${now}-${transientCounter}`;
}

/**
 * Raise a banner.
 *
 * Identity decides dedupe. A banner with a stable identity — a persistent
 * condition, or any banner given a `key` — updates in place, so a retry loop
 * cannot paint ten copies of the same warning. A transient banner with no key is
 * an event ("Added connector X"), so two of them are two facts and both stay.
 */
export function raiseBanner(state: BannerState, spec: BannerSpec, now = Date.now()): BannerState {
  const resolved = resolveSpec(spec);
  const identity = spec.key ?? (resolved.life === "persistent" ? spec.kind : null);
  const banner: Banner = {
    ...resolved,
    id: identity ?? transientId(spec.kind, now),
    raisedAt: now,
  };

  const existing =
    identity === null ? -1 : state.banners.findIndex((entry) => entry.id === identity);
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
 * The visible set, most severe first, capped per dock.
 *
 * Capping per dock matters: the top strip is a page region and the corner stack
 * is a floating one, so a burst of toasts must never hide the strip that says
 * the sidecar is down.
 */
export function selectBanners(
  state: BannerState,
  maxVisible = DEFAULT_MAX_VISIBLE,
): { visible: Banner[]; overflow: number } {
  const bySeverity = (a: Banner, b: Banner) =>
    severityWeight(b.severity) - severityWeight(a.severity) || b.raisedAt - a.raisedAt;

  const top = state.banners.filter((banner) => banner.dock === "top").sort(bySeverity);
  const corner = state.banners.filter((banner) => banner.dock === "corner").sort(bySeverity);

  const visible = [...top.slice(0, maxVisible), ...corner.slice(0, maxVisible)];
  const overflow = Math.max(0, top.length - maxVisible) + Math.max(0, corner.length - maxVisible);
  return { visible, overflow };
}
