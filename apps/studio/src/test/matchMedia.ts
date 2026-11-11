import { vi } from "vitest";

import { LIGHT_QUERY } from "../lib/theme";

/**
 * A `window.matchMedia` whose answer can move while the app is open, the way an
 * operating system's theme setting does at sunset.
 *
 * `set` changes what the query reports, `fire` plays the change event the
 * browser would have sent, and `subscribed` counts the handlers still
 * attached — so a test can prove a subscription both moves the app and ends.
 * `asked` records every query the app brought here, which is how the shipped
 * bootstrap and the live code are held to the same question.
 *
 * `restore` puts the browser's own `matchMedia` back; every caller must run it
 * in `afterEach`, because Vitest shares one window across a file.
 */
export function stubLiveMatchMedia(matches: boolean) {
  const asked: string[] = [];
  const handlers: Array<(event: MediaQueryListEvent) => void> = [];
  const list = {
    media: LIGHT_QUERY,
    matches,
    onchange: null,
    addEventListener: vi.fn((event: string, handler: (event: MediaQueryListEvent) => void) => {
      if (event === "change") {
        handlers.push(handler);
      }
    }),
    removeEventListener: vi.fn((event: string, handler: (event: MediaQueryListEvent) => void) => {
      if (event === "change") {
        handlers.splice(handlers.indexOf(handler), 1);
      }
    }),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(() => false),
  };
  const previous = Object.getOwnPropertyDescriptor(window, "matchMedia");

  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => {
      asked.push(query);
      return list;
    },
  });

  return {
    set(next: boolean): void {
      list.matches = next;
    },
    fire(): void {
      for (const handler of handlers.slice()) {
        handler({ matches: list.matches } as MediaQueryListEvent);
      }
    },
    get subscribed(): number {
      return handlers.length;
    },
    get asked(): string[] {
      return asked;
    },
    restore(): void {
      if (previous) {
        Object.defineProperty(window, "matchMedia", previous);
      } else {
        delete (window as unknown as { matchMedia?: unknown }).matchMedia;
      }
    },
  };
}
