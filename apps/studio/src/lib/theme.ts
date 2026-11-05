import type { StudioTheme, StudioThemePreference } from "../types";
import { useMediaQuery } from "./useMediaQuery";

/** The query every part of the app asks the same question with. */
export const LIGHT_QUERY = "(prefers-color-scheme: light)";

/**
 * What the operating system says right now. `false` when it cannot say: a
 * browser without `matchMedia`, or a test environment that has not been given
 * one. Both answer the same way the app does on a machine with no theme at all
 * — the dark palette, which is the one the stylesheet defines on `:root`.
 */
export function systemPrefersLight(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(LIGHT_QUERY).matches
  );
}

/**
 * The choice to show as checked. A reader who has never opened the theme
 * control and one who picked *Follow the system* want the same behaviour, and
 * the control has to put its dot on one of the three either way — a radio group
 * with nothing checked gives the keyboard no place to start.
 */
export function storedPreference(stored: StudioThemePreference | undefined): StudioThemePreference {
  return stored === "light" || stored === "dark" ? stored : "system";
}

/**
 * The theme to paint: the stored choice when there is one, otherwise what the
 * operating system asks for.
 *
 * This mirrors the inline bootstrap in `index.html`, which resolves the class
 * before the bundle parses so a cold load never flashes the wrong colour. The
 * two must agree on the same inputs or the handover changes colour; the
 * bootstrap is the only place that can run first, so the app follows it here —
 * and it accepts only the two literals, which is why a stored `"system"` and no
 * stored value at all both fall through to the operating system here too.
 *
 * `prefersLight` is the answer the caller already has. It is omitted by
 * surfaces that resolve once per render and read the live query; the provider
 * passes the value its subscription keeps current so a system change repaints
 * without a reload.
 */
export function resolveTheme(
  stored: StudioThemePreference | undefined,
  prefersLight?: boolean,
): StudioTheme {
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return (prefersLight ?? systemPrefersLight()) ? "light" : "dark";
}

/**
 * The palette the operating system wants right now, kept current.
 *
 * `resolveTheme` is a snapshot; this is the subscription the *Follow the
 * system* choice needs, so an OS change at sunset repaints the Studio instead of
 * waiting for the next reload. It belongs to one caller — the provider, which
 * folds it into the theme it paints and publishes. The subscription itself is
 * the one the Studio already uses for `prefers-reduced-motion` and its layout
 * breakpoints; a browser that cannot answer the query is answered the same way
 * everywhere else: dark, no subscription.
 */
export function useSystemTheme(): StudioTheme {
  return useMediaQuery(LIGHT_QUERY) ? "light" : "dark";
}
