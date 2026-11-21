import { afterEach, describe, expect, it, vi } from "vitest";

import { isInstalled } from "./install";

/**
 * `isInstalled()` answers one question — is the page running as its own
 * window? — so a pending install prompt must not change it (#800).
 */
function stubMatchMedia(standalone: boolean) {
  vi.stubGlobal(
    "matchMedia",
    (query: string) => ({
      matches: standalone && query.startsWith("(display-mode:"),
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  );
}

function fireBeforeInstallPrompt() {
  const event = new Event("beforeinstallprompt");
  event.preventDefault = () => {};
  window.dispatchEvent(event);
}

afterEach(() => {
  vi.unstubAllGlobals();
  delete (window.navigator as unknown as { standalone?: boolean }).standalone;
});

describe("isInstalled", () => {
  it.each([true, false])(
    "is unchanged by a pending install prompt when standalone is %s",
    (standalone) => {
      stubMatchMedia(standalone);

      const before = isInstalled();
      fireBeforeInstallPrompt();
      const after = isInstalled();

      expect(after).toBe(before);
      expect(after).toBe(standalone);
    },
  );

  it("reports installed for minimal-ui and fullscreen, not just standalone", () => {
    for (const mode of ["minimal-ui", "fullscreen"]) {
      vi.stubGlobal("matchMedia", (query: string) => ({
        matches: query === `(display-mode: ${mode})`,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }));

      expect(isInstalled()).toBe(true);
    }
  });

  it("falls back to the iOS navigator.standalone flag", () => {
    stubMatchMedia(false);
    (window.navigator as unknown as { standalone?: boolean }).standalone = true;

    expect(isInstalled()).toBe(true);
  });
});
