import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EdgeModelSection } from "./EdgeModelSection";
import type { EdgeNotice, EdgePanelState } from "../edge/manager";
import type { EdgeTierId } from "../edge/types";
import { FLAG_STORAGE_PREFIX, setFeatureOverride } from "../features/flags";

const studio = vi.hoisted(() => ({
  settings: {
    base_url: "http://localhost:8001/v1",
    api_key: "",
    model_name: "",
    mcp_url: "http://localhost:8000/mcp",
  } as Record<string, string>,
}));

vi.mock("../state/StudioContext", () => ({
  useStudio: () => ({ settings: studio.settings }),
}));

const edge = vi.hoisted(() => ({
  panel: null as EdgePanelState | null,
  reads: 0,
  grantAndStart: vi.fn(async () => "t1" as EdgeTierId | null),
  decline: vi.fn(async () => undefined),
  freeTier: vi.fn<(tier: EdgeTierId) => Promise<void>>(async () => undefined),
  servedTier: vi.fn(async () => null as EdgeTierId | null),
  listener: null as ((notice: EdgeNotice) => void) | null,
}));

// Only the manager is doubled: `hasRemoteEndpoint` stays real, because which
// endpoint counts as paid is the routing rule this section has to describe. The
// flag read inside `panelState` is the real one, so the switch is tested through
// the storage it actually writes.
vi.mock("../edge/manager", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../edge/manager")>();
  const { isFeatureEnabled } = await import("../features/flags");
  return {
    ...actual,
    edgeManager: {
      panelState: async () => {
        edge.reads += 1;
        return edge.panel === null
          ? null
          : { ...edge.panel, flagEnabled: isFeatureEnabled("edgeModel") };
      },
      grantAndStart: () => edge.grantAndStart(),
      decline: () => edge.decline(),
      freeTier: (tier: EdgeTierId) => edge.freeTier(tier),
      servedTier: () => edge.servedTier(),
      addNoticeListener: (listener: (notice: EdgeNotice) => void) => {
        edge.listener = listener;
        return () => {
          edge.listener = null;
        };
      },
    },
  };
});

const TIER_FACTS: Record<EdgeTierId, { label: string; approxBytes: number }> = {
  t1: { label: "Llama 3.2 1B", approxBytes: 1_300_000_000 },
  t2: { label: "Llama 3.2 3B", approxBytes: 2_000_000_000 },
  t3: { label: "Llama 3.1 8B", approxBytes: 4_700_000_000 },
};

function tierState(
  id: EdgeTierId,
  overrides: Partial<Omit<EdgePanelState["tiers"][number], "id">> = {},
): EdgePanelState["tiers"][number] {
  return { id, ...TIER_FACTS[id], status: "empty", eligible: true, reason: null, ...overrides };
}

function panelState(overrides: Partial<EdgePanelState> = {}): EdgePanelState {
  return {
    flagEnabled: true,
    consent: "unset",
    tiers: [tierState("t1"), tierState("t2"), tierState("t3")],
    usage: { edgeTurns: 0, streamedSeconds: 0, turnsToNext: 10, secondsToNext: 900 },
    downloadable: true,
    ...overrides,
  };
}

describe("EdgeModelSection", () => {
  beforeEach(() => {
    studio.settings = {
      base_url: "http://localhost:8001/v1",
      api_key: "",
      model_name: "",
      mcp_url: "http://localhost:8000/mcp",
    };
    edge.panel = panelState();
    edge.reads = 0;
    edge.grantAndStart = vi.fn(async () => "t1" as EdgeTierId | null);
    edge.decline = vi.fn(async () => undefined);
    edge.freeTier = vi.fn<(tier: EdgeTierId) => Promise<void>>(async () => undefined);
    edge.servedTier = vi.fn(async () => null as EdgeTierId | null);
    edge.listener = null;
    window.localStorage.clear();
  });

  it("asks for consent in the size of the download, and grants through the manager", async () => {
    render(<EdgeModelSection />);

    const yes = await screen.findByRole("button", {
      name: "Download Llama 3.2 1B — about 1.3 GB, once",
    });
    await act(async () => {
      fireEvent.click(yes);
    });

    expect(edge.grantAndStart).toHaveBeenCalledTimes(1);
  });

  it("lets a person change a refusal, and stops answering on request", async () => {
    edge.panel = panelState({ consent: "denied" });
    const { unmount } = render(<EdgeModelSection />);
    const yes = await screen.findByRole("button", { name: /Download Llama 3.2 1B/ });
    await act(async () => {
      fireEvent.click(yes);
    });
    expect(edge.grantAndStart).toHaveBeenCalledTimes(1);
    unmount();

    edge.panel = panelState({ consent: "granted", tiers: [tierState("t1", { status: "active" })] });
    render(<EdgeModelSection />);
    const stop = await screen.findByRole("button", { name: "Stop answering here" });
    await act(async () => {
      fireEvent.click(stop);
    });
    expect(edge.decline).toHaveBeenCalledTimes(1);
  });

  it("says plainly when consent is granted but a paid key is answering", async () => {
    edge.panel = panelState({ consent: "granted" });
    studio.settings = {
      base_url: "https://api.openai.com/v1",
      api_key: "sk",
      model_name: "gpt",
      mcp_url: "http://localhost:8000/mcp",
    };
    render(<EdgeModelSection />);

    expect(
      await screen.findByText(/your model key is answering for now/i),
    ).toBeInTheDocument();
  });

  it("hides the offer and says so while the switch is off", async () => {
    setFeatureOverride("edgeModel", false);
    render(<EdgeModelSection />);

    const toggle = await screen.findByRole("checkbox");
    expect(toggle).not.toBeChecked();
    expect(screen.getByText(/switched off/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Download Llama/ })).not.toBeInTheDocument();
  });

  it("the switch is the flag: one click turns the feature off for this browser", async () => {
    render(<EdgeModelSection />);
    const toggle = await screen.findByRole("checkbox");
    expect(toggle).toBeChecked();

    await act(async () => {
      fireEvent.click(toggle);
    });

    expect(screen.getByText(/switched off/i)).toBeInTheDocument();
    expect(toggle).not.toBeChecked();
    expect(window.localStorage.getItem(`${FLAG_STORAGE_PREFIX}edgeModel`)).toBe("off");

    await act(async () => {
      fireEvent.click(toggle);
    });
    expect(
      screen.getByRole("button", { name: /Download Llama 3.2 1B/ }),
    ).toBeInTheDocument();
  });

  it("shows each tier's state, and the reason a tier is out of reach", async () => {
    edge.panel = panelState({
      consent: "granted",
      tiers: [
        tierState("t1", { status: "active" }),
        tierState("t2", { status: "cached" }),
        tierState("t3", {
          eligible: false,
          reason: "Needs about a 8 GB-class device; this one reports 4 GB.",
        }),
      ],
    });
    render(<EdgeModelSection />);

    const rows = await screen.findByRole("list");
    expect(within(rows).getByText("answering · about 1.3 GB")).toBeInTheDocument();
    expect(within(rows).getByText("on this device · about 2.0 GB")).toBeInTheDocument();
    expect(
      within(rows).getByText(/Needs about a 8 GB-class device/),
    ).toBeInTheDocument();
    expect(within(rows).getAllByRole("button", { name: /Free the storage/ })).toHaveLength(2);
  });

  it("frees one tier's storage", async () => {
    edge.panel = panelState({ tiers: [tierState("t1", { status: "active" })] });
    render(<EdgeModelSection />);

    const free = await screen.findByRole("button", {
      name: "Free the storage Llama 3.2 1B is using",
    });
    await act(async () => {
      fireEvent.click(free);
    });

    expect(edge.freeTier).toHaveBeenCalledWith("t1");
  });

  it("counts what the next tier still wants, and says when it is earned", async () => {
    edge.panel = panelState({ usage: { edgeTurns: 3, streamedSeconds: 120, turnsToNext: 7, secondsToNext: 780 } });
    render(<EdgeModelSection />);

    expect(await screen.findByRole("meter", { name: /toward the next tier/i })).toHaveAttribute(
      "aria-valuenow",
      "3",
    );
    expect(screen.getByText(/7 more answers, or 13 minutes of streamed replies/i)).toBeInTheDocument();

    edge.panel = panelState({ usage: { edgeTurns: 10, streamedSeconds: 900, turnsToNext: 0, secondsToNext: 0 } });
    await act(async () => {
      edge.listener?.({ kind: "consent-changed" });
    });
    expect(
      screen.getByText(/earned\. the stronger tier arrives the next time this tab is idle/i),
    ).toBeInTheDocument();
  });

  it("re-reads when a tier lands, but not for every percent tick", async () => {
    render(<EdgeModelSection />);
    await screen.findByRole("checkbox");
    const before = edge.reads;

    await act(async () => {
      edge.listener?.({
        kind: "downloading",
        tier: "t2",
        progress: { phase: "download", percent: 0.4, text: "40%" },
      });
    });
    expect(edge.reads).toBe(before);

    edge.panel = panelState({ tiers: [tierState("t1", { status: "active" })] });
    await act(async () => {
      edge.listener?.({ kind: "ready", tier: "t1" });
    });
    expect(screen.getByText(/answering · about 1.3 GB/)).toBeInTheDocument();
    expect(edge.reads).toBeGreaterThan(before);
  });

  it("says when nothing started instead of leaving a yes hanging", async () => {
    edge.grantAndStart = vi.fn(async () => null);
    render(<EdgeModelSection />);

    const yes = await screen.findByRole("button", { name: /Download Llama 3.2 1B/ });
    await act(async () => {
      fireEvent.click(yes);
    });

    expect(screen.getByText(/nothing started in this tab/i)).toBeInTheDocument();
  });

  it("says there is nothing to fetch, and leaves the reason on the tier", async () => {
    edge.panel = panelState({
      downloadable: false,
      tiers: [
        tierState("t1", {
          eligible: false,
          reason: "This browser doesn't support GPU-accelerated models yet.",
        }),
      ],
    });
    render(<EdgeModelSection />);

    expect(await screen.findByText(/can't host any of these models/i)).toBeInTheDocument();
    expect(
      screen.getByText(/doesn't support GPU-accelerated models yet/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Download Llama/ })).not.toBeInTheDocument();
  });

  it("unsubscribes from edge notices when it unmounts", async () => {
    const { unmount } = render(<EdgeModelSection />);
    await screen.findByRole("checkbox");
    expect(edge.listener).toBeTruthy();

    unmount();
    expect(edge.listener).toBeNull();
  });
});
