import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnboardingProvider } from "../onboarding/OnboardingProvider";
import { UpdateProvider, createUpdateService } from "../updater";
import type { UpdateTransport } from "../updater/types";
import { SettingsPanel } from "./SettingsPanel";

vi.mock("../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../state/StudioContext";
import type { StudioContextValue } from "../state/StudioContext";

const transport: UpdateTransport = {
  supported: () => false,
  currentVersion: async () => "0.11.0",
  check: async () => null,
  relaunch: async () => undefined,
};

const service = createUpdateService({
  transport,
  storage: null,
  document: null,
});

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
    recheckConnections: vi.fn().mockResolvedValue(undefined),
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

describe("SettingsPanel model catalog", () => {
  it("offers the endpoint's models as suggestions and keeps typing free", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ models: ["local-tools-model", "qwen3-8b"] }),
    );

    renderPanel();

    const model = screen.getByLabelText(/^model/i);
    expect(model).toHaveAttribute("list", "studio-model-options");
    expect(document.getElementById("studio-model-options")?.children).toHaveLength(2);
    expect(screen.getByText(/2 models available/i)).toBeInTheDocument();
  });

  it("says why there is no catalog instead of pretending the list is empty", () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ models: [], modelsMessage: "connection_error: connection refused", refreshModels: refresh }),
    );

    renderPanel();

    expect(screen.getByLabelText(/^model/i)).not.toHaveAttribute("list");
    expect(screen.getByText(/connection refused/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /find models/i }));
    expect(refresh).toHaveBeenCalled();
  });
});

describe("SettingsPanel connectors", () => {
  it("renders registered connectors and removes one on click", () => {
    const del = vi.fn().mockResolvedValue({ ok: true, name: "notion" });
    vi.mocked(useStudio).mockReturnValue(stubContext({ deleteConnector: del }));

    renderPanel();

    expect(screen.getAllByText(/notion/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /remove notion/i }));
    expect(del).toHaveBeenCalledWith("notion");
  });

  it("groups presets by capability area with id, auth, and a connect control", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectors: [] }));

    renderPanel();

    expect(
      screen.getByRole("region", { name: /voice of customer/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("notion")).toBeInTheDocument();
    expect(screen.getByText(/OAuth/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /connect notion/i })).toBeInTheDocument();
  });

  it("adds a connector from its row", () => {
    const add = vi.fn().mockResolvedValue({ ok: true, name: "notion" });
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ addConnector: add, connectors: [] }),
    );

    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: /connect notion/i }));
    expect(add).toHaveBeenCalledWith({ preset: "notion" });
  });

  it("does not pretend unconnectable sources are connection rows", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    renderPanel();

    expect(screen.queryByText(/gong transcripts/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/slack friction stream/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/product telemetry/i)).not.toBeInTheDocument();
    expect(screen.getByText(/no data source is connected yet/i)).toBeInTheDocument();
  });

  it("toggles API key visibility", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    renderPanel();

    const input = screen.getByLabelText("API key") as HTMLInputElement;
    expect(input.type).toBe("password");

    fireEvent.click(screen.getByRole("button", { name: /show api key/i }));
    expect(input.type).toBe("text");

    fireEvent.click(screen.getByRole("button", { name: /hide api key/i }));
    expect(input.type).toBe("password");
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

  it("offers no connect control while the catalog is in error", () => {
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

    expect(screen.queryByRole("button", { name: /^connect /i })).toBeNull();
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

describe("SettingsPanel about section", () => {
  it("reports the running version, build date, platform, and update status", async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    // A supported transport: the unsupported file-level stub never syncs
    // currentVersion, and About must show real facts, not placeholders.
    const aboutService = createUpdateService({
      transport: {
        supported: () => true,
        currentVersion: async () => "0.11.0",
        check: async () => null,
        relaunch: async () => undefined,
      },
      storage: null,
      document: null,
    });
    render(
      <UpdateProvider service={aboutService}>
        <OnboardingProvider enabled={false}>
          <SettingsPanel />
        </OnboardingProvider>
      </UpdateProvider>,
    );

    const about = screen.getByRole("region", { name: "About" });
    await waitFor(() =>
      expect(aboutService.getSnapshot().currentVersion).toBe("0.11.0"),
    );
    await waitFor(() => expect(aboutService.getSnapshot().phase).not.toBe("checking"));

    expect(within(about).getByText("v0.11.0")).toBeInTheDocument();
    expect(within(about).getByText(__STUDIO_BUILD_DATE__)).toBeInTheDocument();
    expect(within(about).getByText(/macOS|Windows|Linux|Desktop/)).toBeInTheDocument();
    expect(within(about).getByText(aboutService.statusLine())).toBeInTheDocument();
  });
});
