import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FirstRunWizard, OnboardingProvider } from "../../onboarding";
import { UpdateProvider, createUpdateService } from "../../updater";
import type { UpdateTransport } from "../../updater/types";
import { SettingsPanel } from "../SettingsPanel";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";
import type { StudioContextValue } from "../../state/StudioContext";

const transport: UpdateTransport = {
  supported: () => true,
  currentVersion: async () => __STUDIO_APP_VERSION__,
  check: async () => null,
  relaunch: async () => undefined,
};

const service = createUpdateService({ transport, storage: null, document: null });

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    settings: { base_url: "http://x", api_key: "k", model_name: "m", mcp_url: "u", display_name: "" },
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
  it('shows "Take the tour" in exactly one place and opens the tour', async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    renderPanel();

    const tourLinks = screen.getAllByRole("button", { name: "Take the tour" });
    expect(tourLinks).toHaveLength(1);

    fireEvent.click(tourLinks[0]);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("keeps Updates to one state line and at most one action", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    renderPanel();

    const updates = screen.getByRole("region", { name: "Updates" });
    expect(within(updates).getByText(service.statusLine())).toBeInTheDocument();
    expect(within(updates).getAllByRole("button").length).toBeLessThanOrEqual(1);
  });

  it("puts build facts and the product essay in About, not the updater", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    renderPanel();

    const about = screen.getByRole("region", { name: "About" });
    expect(within(about).getByText(`v${__STUDIO_APP_VERSION__}`)).toBeInTheDocument();
    expect(within(about).getByText(__STUDIO_BUILD_COMMIT__)).toBeInTheDocument();
    expect(within(about).getByText(__STUDIO_BUILD_DATE__)).toBeInTheDocument();
    expect(within(about).getByText(/canvas of human intent/i)).toBeInTheDocument();
    // The updater's state stays in the Updates row.
    expect(within(about).queryByText(service.statusLine())).not.toBeInTheDocument();
  });
});
