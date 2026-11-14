import { useMediaQuery } from "./useMediaQuery";

/**
 * Whether the person asked the OS for less motion.
 *
 * CSS honours the preference through the token layer, but motion driven from
 * JavaScript — scroll-to-message, scroll-into-view — cannot read a CSS token,
 * so it asks here instead. A `change` listener means toggling the OS setting
 * takes effect immediately, without a reload.
 */
export function useReducedMotion(): boolean {
  return useMediaQuery("(prefers-reduced-motion: reduce)");
}
