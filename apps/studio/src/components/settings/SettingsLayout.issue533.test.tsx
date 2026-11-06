import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnboardingProvider, FirstRunWizard } from "../../onboarding";
import { UpdateProvider, createUpdateService } from "../../updater";
import { SettingsPanel } from "../SettingsPanel";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";
import type { StudioContextValue } from "../../state/StudioContext";

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    settings: {
      base_url: "http://localhost:8001/v1",
      api_key: "local",
      model_name: "local-tools-model",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    },
    saveSettings: vi.fn(),
    displayName: "Ada",
    setDisplayName: vi.fn(),
    brief: null,
    openSetup: vi.fn(),
    closeSetup: vi.fn(),
    clearChat: vi.fn(),
    refreshCanvas: vi.fn().mockResolvedValue(undefined),
    llmHealth: { healthy: null, message: "" },
    models: [] as string[],
    modelsLoading: false,
    modelsMessage: null as string | null,
    refreshModels: vi.fn().mockResolvedValue(undefined),
    mcpReachable: false,
    sidecarReachable: true,
    pushToast: vi.fn(),
    connectors: [],
    presets: [],
    addConnector: vi.fn().mockResolvedValue({ ok: true, name: "notion" }),
    deleteConnector: vi.fn().mockResolvedValue({ ok: true, name: "notion" }),
    refreshConnectors: vi.fn().mockResolvedValue(undefined),
    refreshPresets: vi.fn().mockResolvedValue(undefined),
    refreshCapabilities: vi.fn().mockResolvedValue(undefined),
    surveyConnections: vi.fn().mockResolvedValue({
      sidecarReachable: true,
      mcpReachable: false,
      llmHealthy: true,
      llmMessage: "ok",
    }),
    capabilities: [],
    ...overrides,
  }) as unknown as StudioContextValue;

function renderPanel() {
  const service = createUpdateService({
    transport: {
      supported: () => true,
      currentVersion: async () => __STUDIO_APP_VERSION__,
      check: async () => null,
      relaunch: async () => undefined,
    },
    storage: null,
    document: null,
  });
  return render(
    <UpdateProvider service={service}>
      <OnboardingProvider enabled={true}>
        <SettingsPanel />
        <FirstRunWizard />
      </OnboardingProvider>
    </UpdateProvider>,
  );
}

describe("Settings layout (#533)", () => {
  it('shows "Take the tour" in exactly one place', () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    renderPanel();

    const tourLinks = screen.getAllByRole("button", { name: "Take the tour" });
    expect(tourLinks).toHaveLength(1);
  });

  it("opens the tour from the single link", async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Take the tour" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("keeps Updates as one state line and at most one action", async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    renderPanel();

    const updates = await screen.findByRole("region", { name: "Updates" });
    await waitFor(() =>
      expect(updates).toHaveTextContent(/up to date|updates|checking|unavailable/i),
    );
    const buttons = within(updates).queryAllByRole("button");
    expect(buttons.length).toBeLessThanOrEqual(1);
  });

  it("puts build facts and the product essay in About", async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    renderPanel();

    const about = screen.getByRole("region", { name: "About" });
    await waitFor(() =>
      expect(within(about).getByText(`v${__STUDIO_APP_VERSION__}`)).toBeInTheDocument(),
    );
    expect(within(about).getByText(__STUDIO_BUILD_DATE__)).toBeInTheDocument();
    expect(within(about).getByText(/dev|[0-9a-f]{7,}/i)).toBeInTheDocument();
    expect(within(about).getByText(/canvas of human intent/i)).toBeInTheDocument();
  });
});
