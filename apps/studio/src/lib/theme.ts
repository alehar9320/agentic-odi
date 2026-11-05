import type { StudioPalette, StudioTheme } from "../types";

/**
 * The theme to paint: the stored choice when it pins one, otherwise what the
 * operating system asks for.
 *
 * This mirrors the inline bootstrap in `index.html`, which resolves the class
 * before the bundle parses so a cold load never flashes the wrong colour. The
 * two must agree on the same inputs or the handover changes colour; the
 * bootstrap is the only place that can run first, so the app follows it here.
 *
 * `prefersLight` is the caller's current answer to the media query. A component
 * that subscribed to it has one in hand and must pass it, or this function reads
 * `matchMedia` again and the value that triggered the render and the value that
 * paints can differ. It is optional only for callers that resolve once, at boot.
 *
 * Anything the app never offered — a hand-edited key, a value from a future
 * build, `null` — falls through to the operating system rather than deciding the
 * palette, so unreadable storage cannot crash the boot.
 */
export function resolveTheme(
  stored: StudioTheme | null | undefined,
  prefersLight?: boolean,
): StudioPalette {
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  if (prefersLight !== undefined) {
    return prefersLight ? "light" : "dark";
  }
  return readPrefersLight() ? "light" : "dark";
}

function readPrefersLight(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: light)").matches
  );
}
