import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BannerBridge, useBannerActionDispatcher } from "./BannerBridge";
import { BannerProvider, useBanner } from "./BannerProvider";
import { BannerStack } from "./BannerStack";

const studio = vi.hoisted(() => ({
  sidecarReachable: true as boolean | null,
  llmHealth: { healthy: true as boolean | null, message: "" },
  streaming: false,
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

/** The update handshake is mocked so a test can stage a build without a worker. */
const swUpdate = vi.hoisted(() => ({
  ready: false,
  dismissed: false,
  dismissAppUpdate: vi.fn(),
  reloadForUpdate: vi.fn(),
}));

vi.mock("../lib/swUpdate", () => ({
  useAppUpdate: () => ({ ready: swUpdate.ready, dismissed: swUpdate.dismissed }),
  dismissAppUpdate: swUpdate.dismissAppUpdate,
  reloadForUpdate: swUpdate.reloadForUpdate,
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
    studio.streaming = false;
    swUpdate.ready = false;
    swUpdate.dismissed = false;
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
    expect(document.querySelectorAll(".banner")).toHaveLength(0);
  });

  it("raises nothing while reachability is still unknown", () => {
    studio.sidecarReachable = null;
    studio.llmHealth = { healthy: null, message: "" };
    renderShell();
    expect(document.querySelectorAll(".banner")).toHaveLength(0);
  });

  it("raises nothing for a supported browser-only state", () => {
    // #507: no sidecar and no model is the browser-only build working as
    // designed, so the bridge must not announce it. This is the rule that fails
    // if a supported-state banner ever returns.
    studio.sidecarReachable = false;
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    expect(document.querySelectorAll(".banner")).toHaveLength(0);
  });

  it("still raises the offline line when the browser has no network", () => {
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

  it("offers a reload once, never a forced one, when a new build is staged", () => {
    swUpdate.ready = true;
    renderShell();

    expect(screen.getByText(/a new version of the studio is ready/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload for the new version" })).toBeInTheDocument();
  });

  it("waits until a streamed turn ends before offering the reload", () => {
    // Reloading under a streaming reply would drop it, so the offer waits.
    studio.streaming = true;
    swUpdate.ready = true;
    const { rerender } = renderShell();
    expect(screen.queryByText(/a new version of the studio is ready/i)).not.toBeInTheDocument();

    studio.streaming = false;
    rerender(
      <BannerProvider>
        <BannerBridge />
        <Shell />
      </BannerProvider>,
    );
    expect(screen.getByText(/a new version of the studio is ready/i)).toBeInTheDocument();
  });

  it("reloads only when the person asks", () => {
    swUpdate.ready = true;
    swUpdate.reloadForUpdate.mockClear();
    renderShell();

    expect(swUpdate.reloadForUpdate).not.toHaveBeenCalled();

    act(() => {
      screen.getByRole("button", { name: "Reload for the new version" }).click();
    });

    expect(swUpdate.reloadForUpdate).toHaveBeenCalledTimes(1);
  });

  it("keeps the reload offer dismissed once the person hides it", () => {
    swUpdate.ready = true;
    swUpdate.dismissAppUpdate.mockClear();
    renderShell();

    act(() => {
      screen.getByRole("button", { name: "Dismiss" }).click();
    });

    expect(swUpdate.dismissAppUpdate).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/a new version of the studio is ready/i)).not.toBeInTheDocument();
  });
});
