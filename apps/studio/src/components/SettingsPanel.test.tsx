import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OnboardingProvider } from "../onboarding/OnboardingProvider";
import { UpdateProvider, createUpdateService } from "../updater";
import type { UpdateTransport } from "../updater/types";
import { SettingsPanel } from "./SettingsPanel";
import { STUDIO_VERSION } from "../lib/version";

vi.mock("../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

vi.mock("../api/studioApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/studioApi")>();
  return {
    ...actual,
    exportWorkspace: vi.fn(),
    importWorkspace: vi.fn(),
    workspaceSummary: vi.fn(),
    readWorkspaceSnapshot: vi.fn(),
  };
});

vi.mock("../lib/download", () => ({ downloadFile: vi.fn() }));

import { useStudio } from "../state/StudioContext";
import type { StudioContextValue } from "../state/StudioContext";
import {
  exportWorkspace,
  importWorkspace,
  readWorkspaceSnapshot,
  workspaceSummary,
} from "../api/studioApi";
import { downloadFile } from "../lib/download";
import type { WorkspaceSummary } from "../bff/store/types";

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

  // #799: in a browser or installed PWA the updater has no version to report,
  // so About used to render "—". It must show the build version instead, and
  // never a dash.
  it("shows the build version when the updater transport is unsupported", async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    const browserService = createUpdateService({
      transport: {
        supported: () => false,
        currentVersion: async () => "0.11.0",
        check: async () => null,
        relaunch: async () => undefined,
      },
      storage: null,
      document: null,
    });
    render(
      <UpdateProvider service={browserService}>
        <OnboardingProvider enabled={false}>
          <SettingsPanel />
        </OnboardingProvider>
      </UpdateProvider>,
    );

    const about = screen.getByRole("region", { name: "About" });
    await waitFor(() => expect(browserService.getSnapshot().phase).not.toBe("checking"));

    expect(within(about).getByText(`v${STUDIO_VERSION}`)).toBeInTheDocument();
    expect(within(about).queryByText("—")).not.toBeInTheDocument();
  });
});

describe("SettingsPanel connection survey", () => {
  it("answers its own rows without telling the rest of the studio", async () => {
    // #309: opening a settings panel is a question about connections, not a request to
    // restyle the window. The measurement belongs to the panel; the recorder that can
    // raise "the sidecar isn't running" only runs when the person presses Recheck.
    const surveyConnections = vi.fn().mockResolvedValue({
      sidecarReachable: false,
      mcpReachable: false,
      llmHealthy: false,
      llmMessage: "connection refused",
    });
    const recheckConnections = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        surveyConnections,
        recheckConnections,
        sidecarReachable: null,
        llmHealth: { healthy: null, message: "" },
      }),
    );

    renderPanel();

    expect(await screen.findByText("unavailable")).toBeInTheDocument();
    expect(surveyConnections).toHaveBeenCalledOnce();
    expect(recheckConnections).not.toHaveBeenCalled();
  });
});

function workspaceSummaryStub(overrides: Partial<WorkspaceSummary["counts"]> = {}) {
  const counts = {
    jobs: 0,
    steps: 0,
    outcomes: 0,
    observations: 0,
    evidence: 0,
    conversations: 0,
    turns: 0,
    ...overrides,
  };
  const records = Object.values(counts).reduce((total, count) => total + count, 0);
  return { records, counts, empty: records === 0 };
}

describe("SettingsPanel workspace export and import", () => {
  beforeEach(() => {
    vi.mocked(exportWorkspace).mockReset();
    vi.mocked(importWorkspace).mockReset();
    vi.mocked(workspaceSummary).mockReset();
    vi.mocked(readWorkspaceSnapshot).mockReset();
    vi.mocked(downloadFile).mockReset();
  });

  it("downloads the whole workspace as one JSON file and reports it", async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    vi.mocked(exportWorkspace).mockResolvedValue('{"version":2}');
    vi.mocked(workspaceSummary).mockResolvedValue(workspaceSummaryStub({ jobs: 2, outcomes: 1 }));

    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: /export my workspace/i }));

    await waitFor(() =>
      expect(downloadFile).toHaveBeenCalledWith(
        '{"version":2}',
        "agentic-odi-workspace.json",
        "application/json",
      ),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(/Exported/);
    expect(screen.getByRole("status")).toHaveTextContent(/2 jobs/);
  });

  it("imports into an empty workspace without asking to replace anything", async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    vi.mocked(readWorkspaceSnapshot).mockResolvedValue({ version: 2 } as never);
    vi.mocked(workspaceSummary)
      .mockResolvedValueOnce(workspaceSummaryStub())
      .mockResolvedValueOnce(workspaceSummaryStub({ jobs: 1 }));
    vi.mocked(importWorkspace).mockResolvedValue(undefined);

    renderPanel();

    const file = new File(['{"version":2}'], "agentic-odi-workspace.json", {
      type: "application/json",
    });
    fireEvent.change(screen.getByLabelText(/import workspace/i), {
      target: { files: [file] },
    });

    await waitFor(() => expect(importWorkspace).toHaveBeenCalledOnce());
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(await screen.findByRole("status")).toHaveTextContent(/Imported/);
  });

  it("asks before replacing a non-empty workspace and cancelling changes nothing", async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    vi.mocked(readWorkspaceSnapshot).mockResolvedValue({ version: 2 } as never);
    vi.mocked(workspaceSummary).mockResolvedValue(workspaceSummaryStub({ jobs: 3, turns: 5 }));

    renderPanel();

    const file = new File(['{"version":2}'], "agentic-odi-workspace.json", {
      type: "application/json",
    });
    fireEvent.change(screen.getByLabelText(/import workspace/i), {
      target: { files: [file] },
    });

    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent(/3 jobs/);
    expect(dialog).toHaveTextContent(/5 messages/);

    fireEvent.click(within(dialog).getByRole("button", { name: /cancel/i }));

    expect(importWorkspace).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("replaces the workspace only after the confirmation is accepted", async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    vi.mocked(readWorkspaceSnapshot).mockResolvedValue({ version: 2 } as never);
    vi.mocked(workspaceSummary)
      .mockResolvedValueOnce(workspaceSummaryStub({ jobs: 1 }))
      .mockResolvedValueOnce(workspaceSummaryStub({ jobs: 4 }));
    vi.mocked(importWorkspace).mockResolvedValue(undefined);

    renderPanel();

    const file = new File(['{"version":2}'], "agentic-odi-workspace.json", {
      type: "application/json",
    });
    fireEvent.change(screen.getByLabelText(/import workspace/i), {
      target: { files: [file] },
    });

    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /replace workspace/i }));

    await waitFor(() => expect(importWorkspace).toHaveBeenCalledOnce());
    expect(await screen.findByRole("status")).toHaveTextContent(/4 jobs/);
  });

  it("reports a version mismatch before anything is replaced", async () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
    vi.mocked(readWorkspaceSnapshot).mockRejectedValue(
      new Error("This workspace file is version 99, but this build reads up to version 2."),
    );

    renderPanel();

    const file = new File(['{"version":99}'], "agentic-odi-workspace.json", {
      type: "application/json",
    });
    fireEvent.change(screen.getByLabelText(/import workspace/i), {
      target: { files: [file] },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(/version 99/);
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(importWorkspace).not.toHaveBeenCalled();
  });
});
