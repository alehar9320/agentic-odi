import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  INSTALL_DISMISSED_KEY,
  createInstallController,
  isInstalled,
  type InstallPromptEvent,
} from "./install";

/** A storage double that only needs the two methods the controller uses. */
function memoryStorage(initial: Record<string, string> = {}) {
  const store = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    has: (key: string) => store.has(key),
    raw: store,
  };
}

/** A minimal window double: listener bookkeeping plus the install signals. */
function fakeWindow(options: { standalone?: boolean; displayModeStandalone?: boolean } = {}) {
  const listeners = new Map<string, Set<(event: Event) => void>>();
  const window = {
    addEventListener: (type: string, listener: (event: Event) => void) => {
      const set = listeners.get(type) ?? new Set();
      set.add(listener);
      listeners.set(type, set);
    },
    removeEventListener: (type: string, listener: (event: Event) => void) => {
      listeners.get(type)?.delete(listener);
    },
    matchMedia: (query: string) => ({
      matches: query === "(display-mode: standalone)" && options.displayModeStandalone === true,
      addEventListener: () => {},
      removeEventListener: () => {},
    }),
    navigator: { standalone: options.standalone === true },
    dispatch: (type: string, event: Event) => {
      for (const listener of listeners.get(type) ?? []) {
        listener(event);
      }
    },
    listenerCount: (type: string) => listeners.get(type)?.size ?? 0,
  };
  return window;
}

/** A `beforeinstallprompt` double that records calls and reports a choice. */
function promptEvent(outcome: "accepted" | "dismissed" = "accepted") {
  const prompt = vi.fn(async () => undefined);
  const event = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), {
    prompt,
    userChoice: Promise.resolve({ outcome, platform: "web" }),
  });
  return { event: event as unknown as InstallPromptEvent, prompt };
}

describe("install controller", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("offers nothing until the browser provides a prompt", () => {
    const controller = createInstallController({
      targetWindow: fakeWindow() as unknown as Window,
      storage: null,
    });

    expect(controller.getSnapshot()).toEqual({ canInstall: false, installed: false });
  });

  it("offers install once the browser has a prompt, and suppresses its own bar", () => {
    const target = fakeWindow();
    const controller = createInstallController({
      targetWindow: target as unknown as Window,
      storage: null,
    });
    const { event } = promptEvent();

    target.dispatch("beforeinstallprompt", event);

    // The browser's mini-infobar is suppressed; the offer is ours to make.
    expect(event.defaultPrevented).toBe(true);
    expect(controller.getSnapshot().canInstall).toBe(true);
  });

  it("resolves with what the person chose and clears the single-use prompt", async () => {
    const target = fakeWindow();
    const controller = createInstallController({
      targetWindow: target as unknown as Window,
      storage: null,
    });
    const { event, prompt } = promptEvent("accepted");
    target.dispatch("beforeinstallprompt", event);

    await expect(controller.prompt()).resolves.toBe("accepted");
    expect(prompt).toHaveBeenCalledOnce();
    // A second click cannot replay a prompt the browser has already retired.
    await expect(controller.prompt()).resolves.toBe("unavailable");
    expect(prompt).toHaveBeenCalledOnce();
  });

  it("remembers a dismissal so the offer is not made again", async () => {
    const target = fakeWindow();
    const storage = memoryStorage();
    const controller = createInstallController({
      targetWindow: target as unknown as Window,
      storage,
    });
    const { event } = promptEvent("dismissed");
    target.dispatch("beforeinstallprompt", event);

    await expect(controller.prompt()).resolves.toBe("dismissed");
    expect(storage.getItem(INSTALL_DISMISSED_KEY)).toBe("1");
    expect(controller.getSnapshot().canInstall).toBe(false);
  });

  it("does not offer install when a dismissal is already remembered", () => {
    const target = fakeWindow();
    const controller = createInstallController({
      targetWindow: target as unknown as Window,
      storage: memoryStorage({ [INSTALL_DISMISSED_KEY]: "1" }),
    });

    target.dispatch("beforeinstallprompt", promptEvent().event);

    expect(controller.getSnapshot().canInstall).toBe(false);
  });

  it("stays silent when the app is already running as an installed window", () => {
    const target = fakeWindow({ displayModeStandalone: true });
    const controller = createInstallController({
      targetWindow: target as unknown as Window,
      storage: null,
    });

    target.dispatch("beforeinstallprompt", promptEvent().event);

    expect(controller.getSnapshot()).toEqual({ canInstall: false, installed: true });
  });

  it("clears the offer once the app is installed", () => {
    const target = fakeWindow();
    const controller = createInstallController({
      targetWindow: target as unknown as Window,
      storage: null,
    });
    target.dispatch("beforeinstallprompt", promptEvent().event);
    expect(controller.getSnapshot().canInstall).toBe(true);

    target.dispatch("appinstalled", new Event("appinstalled"));

    expect(controller.getSnapshot()).toEqual({ canInstall: false, installed: true });
  });

  it("notifies subscribers and detaches on dispose", () => {
    const target = fakeWindow();
    const controller = createInstallController({
      targetWindow: target as unknown as Window,
      storage: null,
    });
    const listener = vi.fn();
    const unsubscribe = controller.subscribe(listener);

    target.dispatch("beforeinstallprompt", promptEvent().event);
    expect(listener).toHaveBeenCalledOnce();

    unsubscribe();
    controller.dispose();
    expect(target.listenerCount("beforeinstallprompt")).toBe(0);
    expect(target.listenerCount("appinstalled")).toBe(0);
  });

  it("reads the installed state from the display mode and iOS's flag", () => {
    expect(isInstalled(null)).toBe(false);
    expect(isInstalled(fakeWindow() as unknown as Window)).toBe(false);
    expect(isInstalled(fakeWindow({ displayModeStandalone: true }) as unknown as Window)).toBe(true);
    expect(isInstalled(fakeWindow({ standalone: true }) as unknown as Window)).toBe(true);
  });

  it("degrades quietly when storage refuses to persist", async () => {
    const storage = {
      getItem: () => null,
      setItem: () => {
        throw new Error("private mode");
      },
    };
    const target = fakeWindow();
    const controller = createInstallController({
      targetWindow: target as unknown as Window,
      storage,
    });
    target.dispatch("beforeinstallprompt", promptEvent("dismissed").event);

    await expect(controller.prompt()).resolves.toBe("dismissed");
    expect(controller.getSnapshot().canInstall).toBe(false);
  });
});

// ---- carried over from main: isInstalled answers one question (#800) ----

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
