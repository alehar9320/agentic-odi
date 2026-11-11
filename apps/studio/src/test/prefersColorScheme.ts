/**
 * Answering the system's colour question in a test.
 *
 * Two documents resolve a theme from `localStorage` plus
 * `(prefers-color-scheme: light)` before any bundle runs — the bootstrap in
 * `index.html` and the offline page. Both guards need the same stubbed answer,
 * so they ask one implementation for it; a stub each test writes for itself can
 * answer the two documents' queries differently and the drift goes unnoticed.
 */
import { LIGHT_QUERY } from "../lib/theme";

const original = window.matchMedia;

/** Make the operating system want light (or not) for the duration of one test. */
export function stubPrefersColorScheme(prefersLight: boolean): void {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches: query === LIGHT_QUERY ? prefersLight : false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

export function restoreMatchMedia(): void {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: original,
  });
}
