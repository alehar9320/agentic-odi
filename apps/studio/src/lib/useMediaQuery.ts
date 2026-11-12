import { useCallback, useSyncExternalStore } from "react";

function queryMatches(query: string): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(query).matches
  );
}

/** The one media query every JS-driven animation is gated on. */
export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * Whether motion should be reduced right now, read outside React.
 *
 * For the imperative edge — a class toggle in an effect — where a hook cannot
 * be called. Anything rendering goes through the hook so one subscription
 * serves the whole page.
 */
export function prefersReducedMotion(): boolean {
  return queryMatches(REDUCED_MOTION_QUERY);
}

/** Subscribe to a CSS media query (SSR/test-safe: false when matchMedia is missing). */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
        return () => {};
      }
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    [query],
  );

  const getSnapshot = useCallback(() => queryMatches(query), [query]);

  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}

/**
 * The single reduced-motion subscription every JS-driven animation reads.
 *
 * One exported hook means one implementation to audit and one place to change;
 * CSS motion stays in the stylesheet's own reduce block.
 */
export function usePrefersReducedMotion(): boolean {
  return useMediaQuery(REDUCED_MOTION_QUERY);
}
