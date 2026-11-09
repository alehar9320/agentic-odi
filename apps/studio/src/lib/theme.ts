import type { StudioTheme } from "../types";

/**
 * The theme to paint: the stored choice when there is one, otherwise what the
 * operating system asks for.
 *
 * This mirrors the inline bootstrap in `index.html`, which resolves the class
 * before the bundle parses so a cold load never flashes the wrong colour. The
 * two must agree on the same inputs or the handover changes colour; the
 * bootstrap is the only place that can run first, so the app follows it here.
 */
export function resolveTheme(stored: StudioTheme | undefined): StudioTheme {
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  if (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: light)").matches
  ) {
    return "light";
  }
  return "dark";
}
