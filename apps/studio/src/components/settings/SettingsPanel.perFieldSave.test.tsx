import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnboardingProvider } from "../../onboarding/OnboardingProvider";
import { UpdateProvider, createUpdateService } from "../../updater";
import type { UpdateTransport } from "../../updater/types";
import { SettingsPanel } from "../SettingsPanel";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";
import type { StudioContextValue } from "../../state/StudioContext";

const transport: UpdateTransport = {
  supported: () => false,
  currentVersion: async () => "0.14.0",
  check: async () => null,
  relaunch: async () => undefined,
};

const service = createUpdateService({ transport, storage: null, document: null });

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
      <OnboardingProvider enabled={false}>
        <SettingsPanel />
      </OnboardingProvider>
    </UpdateProvider>,
  );
}

describe("Settings saves per field", () => {
  it("saves a changed model when the field is left and says so once", () => {
    const saveSettings = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ saveSettings }));

    renderPanel();

    const model = screen.getByLabelText(/^model/i);
    fireEvent.change(model, { target: { value: "qwen3-8b" } });

    // Typing is not saving: the request waits for the field to be left.
    expect(saveSettings).not.toHaveBeenCalled();
    expect(screen.queryByText("Saved")).toBeNull();

    fireEvent.blur(model);

    expect(saveSettings).toHaveBeenCalledTimes(1);
    expect(saveSettings).toHaveBeenCalledWith(
      expect.objectContaining({ model_name: "qwen3-8b" }),
    );
    expect(screen.getByText("Saved")).toBeInTheDocument();
  });

  it("fires no request for an unchanged value", () => {
    const saveSettings = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ saveSettings }));

    renderPanel();

    const model = screen.getByLabelText(/^model/i);
    fireEvent.focus(model);
    fireEvent.blur(model);

    expect(saveSettings).not.toHaveBeenCalled();
    expect(screen.queryByText("Saved")).toBeNull();
  });

  it("refuses an invalid URL beside the field and keeps the old value in use", () => {
    const saveSettings = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ saveSettings }));

    renderPanel();

    const baseUrl = screen.getByLabelText("Base URL");
    fireEvent.change(baseUrl, { target: { value: "not a url" } });
    fireEvent.blur(baseUrl);

    expect(saveSettings).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/not saved/i);
    // The section does not claim success while a field is refused.
    expect(screen.queryByText("Saved")).toBeNull();
  });

  it("refuses a bridge URL that is not an address", () => {
    const saveSettings = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ saveSettings }));

    renderPanel();

    const mcpUrl = screen.getByLabelText("MCP server URL");
    fireEvent.change(mcpUrl, { target: { value: "ftp://nope" } });
    fireEvent.blur(mcpUrl);

    expect(saveSettings).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/not saved/i);
  });

  it("saves the bridge URL on blur, once", () => {
    const saveSettings = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ saveSettings }));

    renderPanel();

    const mcpUrl = screen.getByLabelText("MCP server URL");
    fireEvent.change(mcpUrl, { target: { value: "http://localhost:9000/mcp" } });
    expect(saveSettings).not.toHaveBeenCalled();

    fireEvent.blur(mcpUrl);

    expect(saveSettings).toHaveBeenCalledTimes(1);
    expect(saveSettings).toHaveBeenCalledWith(
      expect.objectContaining({ mcp_url: "http://localhost:9000/mcp" }),
    );
    expect(screen.getByText("Saved")).toBeInTheDocument();
  });

  it("saves a changed API key on blur without validating it", () => {
    const saveSettings = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ saveSettings }));

    renderPanel();

    const apiKey = screen.getByLabelText("API key");
    fireEvent.change(apiKey, { target: { value: "sk-live-123" } });
    fireEvent.blur(apiKey);

    expect(saveSettings).toHaveBeenCalledTimes(1);
    expect(saveSettings).toHaveBeenCalledWith(expect.objectContaining({ api_key: "sk-live-123" }));
  });
});
