import { useCallback, useSyncExternalStore } from "react";

function queryMatches(query: string): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(query).matches
  );
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
 * Whether the person asked for less motion.
 *
 * One hook, inherited by every JS-driven animation. CSS motion keeps its own
 * media block — this is the JS side of the same answer, and a component that
 * needs it reads it here rather than calling `matchMedia` again (#701 D50).
 */
export function usePrefersReducedMotion(): boolean {
  return useMediaQuery("(prefers-reduced-motion: reduce)");
}
