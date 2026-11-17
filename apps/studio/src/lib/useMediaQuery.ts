import { useCallback, useSyncExternalStore } from "react";

/** One breakpoint for the Studio: below it the regions become sheets. */
export const MOBILE_QUERY = "(max-width: 1023px)";

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
