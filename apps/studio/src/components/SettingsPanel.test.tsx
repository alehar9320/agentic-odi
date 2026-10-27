import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnboardingProvider } from "../onboarding/OnboardingProvider";
import { SettingsPanel } from "./SettingsPanel";

vi.mock("../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));
vi.mock("./updater/useUpdater", () => ({
  useUpdater: vi.fn(() => ({
    checking: false,
    available: false,
    version: null,
    progress: null,
    error: null,
    check: vi.fn(),
  })),
}));

import { useStudio } from "../state/StudioContext";
import { useUpdater } from "./updater/useUpdater";
import type { StudioContextValue } from "../state/StudioContext";

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    settings: { base_url: "http://x", api_key: "k", model_name: "m", mcp_url: "u", display_name: "" },
    saveSettings: vi.fn(),
    displayName: "Ada",
    setDisplayName: vi.fn(),
    brief: null,
    openSetup: vi.fn(),
    clearChat: vi.fn(),
    refreshCanvas: vi.fn().mockResolvedValue(undefined),
    llmHealth: { healthy: null, message: "" },
    mcpReachable: false,
    pushToast: vi.fn(),
    connectors: [{ name: "notion", kind: "mcp", enabled: true }],
    presets: [
      {
        id: "notion",
        label: "Notion",
        area: "voice-of-customer",
        summary: "s",
        url: "u",
        auth: "oauth",
        env_vars: [],
        headers: {},
        docs: "d",
        tools: [],
        is_recommended: true,
      },
    ],
    addConnector: vi.fn().mockResolvedValue({ ok: true, name: "notion" }),
    deleteConnector: vi.fn().mockResolvedValue({ ok: true, name: "notion" }),
    refreshConnectors: vi.fn().mockResolvedValue(undefined),
    refreshPresets: vi.fn().mockResolvedValue(undefined),
    refreshCapabilities: vi.fn().mockResolvedValue(undefined),
    capabilities: [],
    ...overrides,
  }) as unknown as StudioContextValue;

function renderPanel() {
  return render(
    <OnboardingProvider enabled={false}>
      <SettingsPanel />
    </OnboardingProvider>,
  );
}

describe("SettingsPanel connectors", () => {
  it("renders registered connectors and removes one on click", () => {
    const del = vi.fn().mockResolvedValue({ ok: true, name: "notion" });
    vi.mocked(useStudio).mockReturnValue(stubContext({ deleteConnector: del }));

    renderPanel();

    expect(screen.getByText(/notion/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /remove notion/i }));
    expect(del).toHaveBeenCalledWith("notion");
  });

  it("adds a connector from a selected preset", () => {
    const add = vi.fn().mockResolvedValue({ ok: true, name: "notion" });
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ addConnector: add, connectors: [] }),
    );

    renderPanel();

    fireEvent.change(screen.getByRole("combobox", { name: /add preset/i }), {
      target: { value: "notion" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add preset/i }));
    expect(add).toHaveBeenCalledWith({ preset: "notion" });
  });

  it("leaves update errors inline instead of toasting them", () => {
    const pushToast = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ pushToast }));
    vi.mocked(useUpdater).mockReturnValueOnce({
      checking: false,
      available: false,
      version: null,
      progress: null,
      error: "Update check failed.",
      check: vi.fn(),
    });

    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: /check for updates/i }));

    expect(pushToast).not.toHaveBeenCalled();
  });

  it("shows an empty state when no connectors are registered", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectors: [] }));

    renderPanel();

    expect(screen.getByText(/no connectors registered/i)).toBeInTheDocument();
  });
});

describe("SettingsPanel connector catalog failures", () => {
  it("shows the catalog failure with a retry instead of an empty select", () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        presets: [],
        presetError: {
          code: "mcp_unreachable",
          message: "The connector catalog is unreachable.",
          suggestion: "Check that the sidecar is running, then try again.",
          retryable: true,
        },
        refreshPresets: refresh,
      }),
    );

    renderPanel();

    expect(screen.getByRole("alert").textContent).toContain(
      "The connector catalog is unreachable.",
    );

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refresh).toHaveBeenCalled();
  });

  it("disables adding a preset while the catalog is in error", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        presets: [],
        presetError: {
          code: "mcp_unreachable",
          message: "The connector catalog is unreachable.",
          retryable: true,
        },
      }),
    );

    renderPanel();

    expect(screen.getByRole("button", { name: /add preset/i })).toBeDisabled();
  });
});

describe("SettingsPanel connector list failures", () => {
  it("shows the failure instead of claiming there are no connectors", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        connectors: [],
        connectorsError: {
          code: "mcp_unreachable",
          message: "The connector list is unreachable.",
          suggestion: "Check that the sidecar is running, then try again.",
          retryable: true,
        },
      }),
    );

    renderPanel();

    expect(screen.getByRole("alert").textContent).toContain("The connector list is unreachable.");
    expect(screen.queryByText(/no connectors registered/i)).toBeNull();
  });
});

describe("SettingsPanel capabilities", () => {
  it("renders each capability with its status", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        capabilities: [
          {
            id: "local-data",
            label: "Local canvas data",
            description: "Jobs, steps, and outcomes stored in your browser.",
            status: "available",
          },
          {
            id: "sidecar-llm",
            label: "Sidecar model proxy",
            description: "Streams model responses through the local Python sidecar.",
            status: "unavailable",
            reason: "Sidecar unreachable.",
          },
        ],
      }),
    );

    renderPanel();

    const dataRow = screen.getByText(/local canvas data/i).closest("li");
    expect(dataRow).toBeInTheDocument();
    expect(dataRow).toHaveTextContent("available");

    const llmRow = screen.getByText(/sidecar model proxy/i).closest("li");
    expect(llmRow).toBeInTheDocument();
    expect(llmRow).toHaveTextContent(/unavailable/);
  });
});
