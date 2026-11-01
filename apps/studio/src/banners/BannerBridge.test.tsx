import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BannerBridge, useBannerActionDispatcher } from "./BannerBridge";
import { BannerProvider, useBanner } from "./BannerProvider";
import { BannerStack } from "./BannerStack";
import type { EdgeNotice, EdgeOffer } from "../edge/manager";
import type { EdgeTierId } from "../edge/types";

const studio = vi.hoisted(() => ({
  sidecarReachable: true as boolean | null,
  llmHealth: { healthy: true as boolean | null, message: "" },
  dismissedSidecarNotice: false,
  settings: {
    base_url: "http://localhost:8001/v1",
    api_key: "",
    model_name: "",
    mcp_url: "http://localhost:8000/mcp",
  },
  dismissSidecarNotice: vi.fn(),
  recheckConnections: vi.fn(),
  openSetup: vi.fn(),
  openPanel: vi.fn(),
  ask: vi.fn(),
}));

vi.mock("../state/StudioContext", () => ({
  useStudio: () => studio,
}));

const edge = vi.hoisted(() => ({
  sync: vi.fn(async () => undefined),
  canServe: vi.fn(() => false),
  offerFor: vi.fn(async () => null as EdgeOffer | null),
  grantAndStart: vi.fn(async () => "t1" as EdgeTierId | null),
  decline: vi.fn(async () => undefined),
  servedTier: vi.fn(async () => null as EdgeTierId | null),
  isBusy: vi.fn(() => false),
  noticeListener: null as ((notice: EdgeNotice) => void) | null,
}));

vi.mock("../edge/manager", async () => {
  // The bridge defers to the studio's one endpoint rule, so the rule stays
  // real here: mocking it would let this suite pass while production defers
  // to something else. It lives in `lib/modelEndpoint`, not in the manager.
  const { isEndpointConfiguredForSettings } = await import("../lib/modelEndpoint");
  return {
    hasModelEndpoint: (settings: { base_url: string; api_key: string; model_name: string }) =>
      isEndpointConfiguredForSettings(settings),
    edgeManager: {
      sync: () => edge.sync(),
      canServe: (...args: unknown[]) => edge.canServe(...(args as [])),
      offerFor: (...args: unknown[]) => edge.offerFor(...(args as [])),
      grantAndStart: () => edge.grantAndStart(),
      decline: () => edge.decline(),
      servedTier: () => edge.servedTier(),
      isBusy: () => edge.isBusy(),
      addNoticeListener: (listener: (notice: EdgeNotice) => void) => {
        edge.noticeListener = listener;
        return () => {
          edge.noticeListener = null;
        };
      },
    },
  };
});

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
    edge.sync = vi.fn(async () => undefined);
    edge.canServe = vi.fn(() => false);
    edge.offerFor = vi.fn(async () => null);
    edge.grantAndStart = vi.fn(async () => "t1");
    edge.decline = vi.fn(async () => undefined);
    edge.servedTier = vi.fn(async () => null);
    edge.isBusy = vi.fn(() => false);
    edge.noticeListener = null;
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

  it("raises a working-by-hand strip when no model is reachable", async () => {
    studio.sidecarReachable = true;
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() => expect(screen.getByText(/Working by hand/i)).toBeInTheDocument());
  });

  it("keeps the working-by-hand strip away when the browser can answer instead", async () => {
    edge.canServe = vi.fn(() => true);
    studio.sidecarReachable = true;
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() => expect(edge.canServe).toHaveBeenCalled());
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
  });

  it("asks for consent instead of working by hand, on a device that could host a tier", async () => {
    edge.offerFor = vi.fn(async () => ({
      tier: "t1",
      label: "Llama 3.2 1B",
      approxBytes: 1_300_000_000,
    }));
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() =>
      expect(screen.getByText(/This browser can answer, free/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/about 1.3 GB, once/)).toBeInTheDocument();
    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
  });

  it("asks a browser-only first run, which has no measurement to wait for", async () => {
    // The defect this case pins: the studio's background survey deliberately
    // refuses to record "the model is down" for a visitor who never configured
    // a model (#309 — no apology on a first run). Gating the consent offer on
    // that measurement meant the offer was only ever shown to someone who had
    // a paid model and lost it. Nothing is answering, and that is enough.
    edge.offerFor = vi.fn(async () => ({
      tier: "t1",
      label: "Llama 3.2 1B",
      approxBytes: 1_300_000_000,
    }));
    studio.sidecarReachable = null;
    studio.llmHealth = { healthy: null, message: "" };
    renderShell();
    await waitFor(() =>
      expect(screen.getByText(/This browser can answer, free/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
  });

  it("says nothing to a browser-only first run whose device could not host a tier", async () => {
    // The other half: widening the offer question must not widen the apology.
    // An unmeasured model is not a broken model.
    studio.sidecarReachable = null;
    studio.llmHealth = { healthy: null, message: "" };
    renderShell();
    await waitFor(() => expect(edge.canServe).toHaveBeenCalled());
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/This browser can answer, free/i)).not.toBeInTheDocument();
  });

  it("never offers the browser model to a device that could not host one", async () => {
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() => expect(screen.getByText(/Working by hand/i)).toBeInTheDocument());
    expect(screen.queryByText(/This browser can answer, free/i)).not.toBeInTheDocument();
  });

  it("goes quiet instead of claiming no model is reachable while the consented fetch runs", async () => {
    edge.isBusy = vi.fn(() => true);
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() => expect(edge.canServe).toHaveBeenCalled());
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/This browser can answer, free/i)).not.toBeInTheDocument();
  });

  it("celebrates the first tier landing, then stops asking", async () => {
    edge.offerFor = vi.fn(async () => ({
      tier: "t1",
      label: "Llama 3.2 1B",
      approxBytes: 1_300_000_000,
    }));
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() =>
      expect(screen.getByText(/This browser can answer, free/i)).toBeInTheDocument(),
    );

    edge.canServe = vi.fn(() => true);
    edge.offerFor = vi.fn(async () => null);
    act(() => {
      edge.noticeListener?.({ kind: "ready", tier: "t1" });
    });
    await waitFor(() =>
      expect(screen.queryByText(/This browser can answer, free/i)).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/Llama 3.2 1B is answering in this tab now/i)).toBeInTheDocument();
  });

  it("goes and looks again when another tab moved the ladder, without cheering someone else's download", async () => {
    edge.offerFor = vi.fn(async () => ({
      tier: "t1",
      label: "Llama 3.2 1B",
      approxBytes: 1_300_000_000,
    }));
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() =>
      expect(screen.getByText(/This browser can answer, free/i)).toBeInTheDocument(),
    );

    // The other tab said yes and fetched it. This tab's job is to find that
    // out, stop asking, and claim none of the credit for the download.
    edge.canServe = vi.fn(() => true);
    edge.offerFor = vi.fn(async () => null);
    const readsBefore = edge.sync.mock.calls.length;
    act(() => {
      edge.noticeListener?.({ kind: "changed" });
    });

    await waitFor(() =>
      expect(screen.queryByText(/This browser can answer, free/i)).not.toBeInTheDocument(),
    );
    expect(edge.sync.mock.calls.length).toBeGreaterThan(readsBefore);
    expect(screen.queryByText(/answering in this tab now/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
  });

  it("says so when a yes does not start a download", async () => {
    edge.offerFor = vi.fn(async () => ({
      tier: "t1",
      label: "Llama 3.2 1B",
      approxBytes: 1_300_000_000,
    }));
    edge.grantAndStart = vi.fn(async () => null);
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() =>
      expect(screen.getByText(/This browser can answer, free/i)).toBeInTheDocument(),
    );

    act(() => {
      screen.getByRole("button", { name: "Answer in this browser" }).click();
    });
    await waitFor(() =>
      expect(screen.getByText(/That download didn't start/i)).toBeInTheDocument(),
    );
  });

  it("stays quiet when a yes finds the model already on its way from another tab", async () => {
    edge.offerFor = vi.fn(async () => ({
      tier: "t1",
      label: "Llama 3.2 1B",
      approxBytes: 1_300_000_000,
    }));
    edge.grantAndStart = vi.fn(async () => null);
    edge.servedTier = vi.fn(async () => "t1");
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() =>
      expect(screen.getByText(/This browser can answer, free/i)).toBeInTheDocument(),
    );

    act(() => {
      screen.getByRole("button", { name: "Answer in this browser" }).click();
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.queryByText(/didn't start/i)).not.toBeInTheDocument();
  });

  it("sends a \"Not now\" to durable consent, so the studio asks once", async () => {
    edge.offerFor = vi.fn(async () => ({
      tier: "t1",
      label: "Llama 3.2 1B",
      approxBytes: 1_300_000_000,
    }));
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() =>
      expect(screen.getByText(/This browser can answer, free/i)).toBeInTheDocument(),
    );

    act(() => {
      screen.getByRole("button", { name: "Not now" }).click();
    });
    expect(edge.decline).toHaveBeenCalledTimes(1);
  });

  it("sends \"Answer in this browser\" to consent plus the first download", async () => {
    edge.offerFor = vi.fn(async () => ({
      tier: "t1",
      label: "Llama 3.2 1B",
      approxBytes: 1_300_000_000,
    }));
    studio.llmHealth = { healthy: false, message: "no model" };
    renderShell();
    await waitFor(() =>
      expect(screen.getByText(/This browser can answer, free/i)).toBeInTheDocument(),
    );

    act(() => {
      screen.getByRole("button", { name: "Answer in this browser" }).click();
    });
    expect(edge.grantAndStart).toHaveBeenCalledTimes(1);
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

  it("raises one strip per download and updates it in place as progress arrives", async () => {
    renderShell();
    await act(async () => {});
    expect(edge.noticeListener).toBeTruthy();

    act(() => {
      edge.noticeListener?.({
        kind: "downloading",
        tier: "t2",
        progress: { phase: "download", percent: 0.42, text: "42%" },
      });
    });
    expect(screen.getByText(/Making this browser smarter, quietly/i)).toBeInTheDocument();
    expect(screen.getByText(/Fetching Llama 3.2 3B \(42%\)/)).toBeInTheDocument();

    act(() => {
      edge.noticeListener?.({
        kind: "downloading",
        tier: "t2",
        progress: { phase: "download", percent: 0.7, text: "70%" },
      });
    });
    expect(screen.getByText(/Fetching Llama 3.2 3B \(70%\)/)).toBeInTheDocument();
    expect(screen.queryByText(/42%/)).not.toBeInTheDocument();
    expect(
      screen.getAllByText(/Making this browser smarter, quietly/i),
    ).toHaveLength(1);
  });

  it("clears the download strip and celebrates when a tier unlocks", async () => {
    renderShell();
    await act(async () => {});

    act(() => {
      edge.noticeListener?.({
        kind: "downloading",
        tier: "t2",
        progress: { phase: "download", percent: 0.5, text: "50%" },
      });
    });
    expect(screen.getByText(/Making this browser smarter, quietly/i)).toBeInTheDocument();

    act(() => {
      edge.noticeListener?.({ kind: "unlocked", tier: "t2" });
    });
    expect(screen.queryByText(/Making this browser smarter, quietly/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Your replies just got smarter/i)).toBeInTheDocument();
    expect(screen.getByText(/Llama 3.2 3B is answering in this browser now/i)).toBeInTheDocument();
  });

  it("unsubscribes from edge notices when the bridge unmounts", () => {
    const { unmount } = renderShell();
    expect(edge.noticeListener).toBeTruthy();

    unmount();
    expect(edge.noticeListener).toBeNull();
  });
});
