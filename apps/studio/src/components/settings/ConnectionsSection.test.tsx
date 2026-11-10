import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ConnectorPreset, StudioConfig, StudioError } from "../../types";
import { ConnectionsSection } from "./sections/ConnectionsSection";
import { ModelSection } from "./sections/ModelSection";

const settings: StudioConfig = {
  base_url: "http://localhost:8001/v1",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
};

const preset: ConnectorPreset = {
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
};

const connectorError: StudioError = {
  code: "mcp_unreachable",
  message: "The connector list is unreachable.",
  suggestion: "Check that the sidecar is running, then try again.",
  retryable: true,
};

function renderSection(overrides: Partial<Parameters<typeof ConnectionsSection>[0]> = {}) {
  const props = {
    settings,
    saveSettings: vi.fn(),
    modelHealthy: true as boolean | null,
    sidecarKnown: true as boolean | null,
    mcpKnown: true,
    capabilities: [],
    connectors: [],
    connectorsError: null as StudioError | null,
    connectorsLoading: false,
    presets: [] as ConnectorPreset[],
    presetError: null as StudioError | null,
    presetsLoading: false,
    refreshConnectors: vi.fn().mockResolvedValue(undefined),
    refreshPresets: vi.fn().mockResolvedValue(undefined),
    addConnector: vi.fn().mockResolvedValue(undefined),
    deleteConnector: vi.fn().mockResolvedValue(undefined),
    openCustomize: vi.fn(),
    ...overrides,
  };
  return { ...render(<ConnectionsSection {...props} />), props };
}

describe("ConnectionsSection", () => {
  it("renders the status rows and capability rows", () => {
    renderSection({
      modelHealthy: false,
      sidecarKnown: null,
      mcpKnown: false,
      capabilities: [
        {
          id: "local-data",
          label: "Local canvas data",
          description: "Jobs stored in your browser.",
          status: "available",
        },
        {
          id: "sidecar-llm",
          label: "Sidecar model proxy",
          description: "Streams through the sidecar.",
          status: "unavailable",
          reason: "Sidecar unreachable.",
        },
      ],
    });

    expect(screen.getByText("Model").closest("li")).toHaveTextContent("offline");
    expect(screen.getByText("Sidecar").closest("li")).toHaveTextContent("unknown");
    expect(screen.getByText("Local FastMCP server").closest("li")).toHaveTextContent("offline");
    expect(screen.getByText(/local canvas data/i).closest("li")).toHaveTextContent("available");
    expect(screen.getByText(/sidecar model proxy/i).closest("li")).toHaveTextContent(/unavailable/);
  });

  it("shows the connector list failure with a retry instead of an empty list", () => {
    const refreshConnectors = vi.fn().mockResolvedValue(undefined);
    renderSection({ connectors: [], connectorsError: connectorError, refreshConnectors });

    expect(screen.getByRole("alert").textContent).toContain("The connector list is unreachable.");
    expect(screen.queryByText(/no connectors registered/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refreshConnectors).toHaveBeenCalled();
  });

  it("shows the catalog failure with a retry instead of an empty catalog", () => {
    const refreshPresets = vi.fn().mockResolvedValue(undefined);
    renderSection({
      presets: [],
      presetError: {
        code: "mcp_unreachable",
        message: "The connector catalog is unreachable.",
        retryable: true,
      },
      refreshPresets,
    });

    expect(screen.getByRole("alert").textContent).toContain(
      "The connector catalog is unreachable.",
    );
    expect(screen.queryByRole("button", { name: /^connect /i })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refreshPresets).toHaveBeenCalled();
  });

  it("says it is still reading rather than claiming the list is empty", () => {
    renderSection({ connectorsLoading: true });

    expect(screen.getByText(/reading the connector list/i)).toBeInTheDocument();
    expect(screen.queryByText(/no connectors registered/i)).toBeNull();
  });

  it("groups presets by capability area and connects one from its row", () => {
    const addConnector = vi.fn().mockResolvedValue(undefined);
    renderSection({ presets: [preset], addConnector });

    expect(screen.getByRole("region", { name: /voice of customer/i })).toBeInTheDocument();
    expect(screen.getByText(/OAuth/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /connect notion/i }));
    expect(addConnector).toHaveBeenCalledWith({ preset: "notion" });
  });

  it("saves the bridge URL on blur, once", () => {
    const { props } = renderSection();

    const mcpUrl = screen.getByLabelText("MCP server URL");
    fireEvent.change(mcpUrl, { target: { value: "http://localhost:9000/mcp" } });
    expect(props.saveSettings).not.toHaveBeenCalled();

    fireEvent.blur(mcpUrl);

    expect(props.saveSettings).toHaveBeenCalledTimes(1);
    expect(props.saveSettings).toHaveBeenCalledWith(
      expect.objectContaining({ mcp_url: "http://localhost:9000/mcp" }),
    );
  });

  it("keeps the Model section intact when the connector fetch fails", () => {
    // The failure-isolation contract: both sections are composed from props,
    // no provider between them, so a broken connector fetch stays in
    // Connections and the model controls beside it keep working.
    render(
      <div>
        <ModelSection
          settings={settings}
          saveSettings={vi.fn()}
          models={["local-tools-model"]}
          modelsLoading={false}
          modelsMessage={null}
          refreshModels={vi.fn()}
        />
        <ConnectionsSection
          settings={settings}
          saveSettings={vi.fn()}
          modelHealthy={true}
          sidecarKnown={true}
          mcpKnown={true}
          capabilities={[]}
          connectors={[]}
          connectorsError={connectorError}
          connectorsLoading={false}
          presets={[]}
          presetError={null}
          presetsLoading={false}
          refreshConnectors={vi.fn()}
          refreshPresets={vi.fn()}
          addConnector={vi.fn()}
          deleteConnector={vi.fn()}
          openCustomize={vi.fn()}
        />
      </div>,
    );

    expect(screen.getByRole("alert").textContent).toContain("The connector list is unreachable.");
    expect(screen.getByLabelText(/^model/i)).toHaveValue("local-tools-model");
    expect(screen.getByLabelText("Base URL")).toHaveValue("http://localhost:8001/v1");
  });
});
