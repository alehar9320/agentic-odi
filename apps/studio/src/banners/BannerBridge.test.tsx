import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BannerBridge, useBannerActionDispatcher } from "./BannerBridge";
import { BannerProvider, useBanner } from "./BannerProvider";
import { BannerStack } from "./BannerStack";

const studio = vi.hoisted(() => ({
  sidecarReachable: true as boolean | null,
  llmHealth: { healthy: true as boolean | null, message: "" },
  dismissedSidecarNotice: false,
  dismissSidecarNotice: vi.fn(),
  recheckConnections: vi.fn(),
  openSetup: vi.fn(),
  openPanel: vi.fn(),
  ask: vi.fn(),
}));

const originalOnLine = Object.getOwnPropertyDescriptor(window.navigator, "onLine");

/** jsdom reports `onLine: true`; the offline path needs to flip it and dispatch
 * the event the bridge subscribes to. */
function setOnLine(value: boolean) {
  Object.defineProperty(window.navigator, "onLine", { value, configurable: true });
}

function goOffline() {
  setOnLine(false);
  act(() => {
    window.dispatchEvent(new Event("offline"));
  });
}

function goOnline() {
  setOnLine(true);
  act(() => {
    window.dispatchEvent(new Event("online"));
  });
}

vi.mock("../state/StudioContext", () => ({
  useStudio: () => studio,
}));

/** The real shell wiring: bridge in, dispatcher out. */
function Shell() {
  const { view } = useBanner();
  const { onIntent, onAction, onDismiss } = useBannerActionDispatcher();
  return (
    <BannerStack
      banners={view.visible}
      overflow={view.overflow}
      onDismiss={onDismiss}
      onAction={onAction}
      onIntent={onIntent}
    />
  );
}

function renderShell() {
  return render(
    <BannerProvider>
      <BannerBridge />
      <Shell />
    </BannerProvider>,
  );
}

describe("BannerBridge", () => {
  beforeEach(() => {
    studio.sidecarReachable = true;
    studio.llmHealth = { healthy: true, message: "" };
    studio.dismissedSidecarNotice = false;
    setOnLine(true);
  });

  afterEach(() => {
    setOnLine(true);
    if (originalOnLine) {
      Object.defineProperty(window.navigator, "onLine", originalOnLine);
    }
  });

  it("raises nothing while the sidecar is reachable and the model is healthy", () => {
    studio.sidecarReachable = true;
    studio.llmHealth = { healthy: true, message: "" };
    renderShell();
    expect(screen.queryByText(/sidecar isn't running/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
  });

  it("raises nothing while reachability is still unknown", () => {
    studio.sidecarReachable = null;
    studio.llmHealth = { healthy: null, message: "" };
    renderShell();
    expect(screen.queryByText(/sidecar isn't running/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
  });

  it("raises a strip when the sidecar is down", () => {
    studio.sidecarReachable = false;
    studio.llmHealth = { healthy: true, message: "" };
    renderShell();
    expect(screen.getByText(/sidecar isn't running/i)).toBeInTheDocument();
  });

  it("clears the strip when the sidecar comes back", () => {
    studio.sidecarReachable = false;
    studio.llmHealth = { healthy: true, message: "" };
    const { rerender } = renderShell();
    expect(screen.getByText(/sidecar isn't running/i)).toBeInTheDocument();

    studio.sidecarReachable = true;
    rerender(
      <BannerProvider>
        <BannerBridge />
        <Shell />
      </BannerProvider>,
    );
    expect(screen.queryByText(/sidecar isn't running/i)).not.toBeInTheDocument();
  });

  it("does not raise the strip once the user dismissed it this session", () => {
    studio.sidecarReachable = false;
    studio.dismissedSidecarNotice = true;
    studio.llmHealth = { healthy: true, message: "" };
    renderShell();
    expect(screen.queryByText(/sidecar isn't running/i)).not.toBeInTheDocument();
  });

  it("raises a working-by-hand strip when no model is reachable", () => {
    studio.sidecarReachable = true;
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    expect(screen.getByText(/Working by hand/i)).toBeInTheDocument();
  });

  it("rechecks the sidecar through the real dispatcher", () => {
    studio.sidecarReachable = false;
    studio.llmHealth = { healthy: true, message: "" };
    studio.recheckConnections.mockClear();
    renderShell();

    act(() => {
      screen.getByRole("button", { name: "Recheck" }).click();
    });

    expect(studio.recheckConnections).toHaveBeenCalledTimes(1);
  });

  it("opens setup through the real dispatcher", () => {
    studio.sidecarReachable = false;
    studio.llmHealth = { healthy: true, message: "" };
    studio.openSetup.mockClear();
    renderShell();

    act(() => {
      screen.getByRole("button", { name: "Start the sidecar" }).click();
    });

    expect(studio.openSetup).toHaveBeenCalledTimes(1);
  });

  it("clears the strip from the store when the user dismisses it", () => {
    studio.sidecarReachable = false;
    studio.dismissedSidecarNotice = false;
    studio.llmHealth = { healthy: true, message: "" };
    renderShell();
    expect(screen.getByText(/sidecar isn't running/i)).toBeInTheDocument();

    act(() => {
      screen.getByRole("button", { name: "Dismiss" }).click();
    });

    expect(screen.queryByText(/sidecar isn't running/i)).not.toBeInTheDocument();
  });

  it("persists the sidecar dismissal, so the strip does not come back", () => {
    studio.sidecarReachable = false;
    studio.dismissedSidecarNotice = false;
    studio.llmHealth = { healthy: true, message: "" };
    studio.dismissSidecarNotice.mockClear();
    renderShell();

    act(() => {
      screen.getByRole("button", { name: "Dismiss" }).click();
    });

    expect(studio.dismissSidecarNotice).toHaveBeenCalledTimes(1);
  });

  it("says one line naming what still works when the browser goes offline", () => {
    renderShell();
    expect(screen.queryByText(/you're offline/i)).not.toBeInTheDocument();

    goOffline();

    expect(screen.getByText(/you're offline/i)).toBeInTheDocument();
    expect(screen.getByText(/on this device/i)).toBeInTheDocument();
  });

  it("does not repeat the offline line when the connection flaps", () => {
    renderShell();
    goOffline();
    goOnline();
    goOffline();

    expect(screen.getAllByText(/you're offline/i)).toHaveLength(1);
  });

  it("clears the offline line when the connection comes back", () => {
    renderShell();
    goOffline();
    expect(screen.getByText(/you're offline/i)).toBeInTheDocument();

    goOnline();

    expect(screen.queryByText(/you're offline/i)).not.toBeInTheDocument();
  });

  it("says offline rather than working-by-hand while the browser has no network", () => {
    // One condition, one line: the offline strip already names what still works,
    // so the model strip would only repeat it.
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    goOffline();

    expect(screen.getByText(/you're offline/i)).toBeInTheDocument();
    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
  });

  it("brings back the working-by-hand line once the browser is back online", () => {
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    goOffline();
    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();

    goOnline();

    expect(screen.getByText(/Working by hand/i)).toBeInTheDocument();
  });

  it("keeps the offline line alone while the browser has no network", () => {
    // The sidecar strip's Recheck and Start actions could not succeed offline,
    // so it waits until the connection is back.
    studio.sidecarReachable = false;
    renderShell();
    goOffline();

    expect(screen.getByText(/you're offline/i)).toBeInTheDocument();
    expect(screen.queryByText(/sidecar isn't running/i)).not.toBeInTheDocument();

    goOnline();

    expect(screen.getByText(/sidecar isn't running/i)).toBeInTheDocument();
  });
});
