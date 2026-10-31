import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OnboardingProvider } from "../onboarding/OnboardingProvider";
import { UpdateProvider, createUpdateService } from "../updater";
import type { UpdateTransport } from "../updater/types";
import { SettingsPanel } from "../components/SettingsPanel";
import { useStudio } from "../state/StudioContext";
import type { StudioContextValue } from "../state/StudioContext";
import { DiagnosticsModal } from "./DiagnosticsModal";

vi.mock("../state/StudioContext", () => ({ useStudio: vi.fn() }));

const modalProps = {
  json: '{\n  "schema": 1\n}',
  byteCount: 16,
  entryCount: 0,
  engineAvailable: false,
  onClose: vi.fn(),
};

const transport: UpdateTransport = {
  supported: () => false,
  currentVersion: async () => "0.14.0",
  check: async () => null,
  relaunch: async () => undefined,
};

const service = createUpdateService({ transport, storage: null, document: null });

function stubContext(): StudioContextValue {
  return {
    settings: {
      base_url: "http://localhost:8001/v1",
      api_key: "local-secret",
      model_name: "model",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    },
    saveSettings: vi.fn(),
    displayName: "",
    setDisplayName: vi.fn(),
    brief: null,
    canvasState: { kind: "ready", data: null },
    openSetup: vi.fn(),
    closeSetup: vi.fn(),
    clearChat: vi.fn(),
    refreshCanvas: vi.fn().mockResolvedValue(undefined),
    llmHealth: { healthy: null, message: "" },
    models: [],
    modelsLoading: false,
    modelsMessage: null,
    refreshModels: vi.fn().mockResolvedValue(undefined),
    mcpReachable: false,
    sidecarReachable: false,
    connectors: [],
    presets: [],
    addConnector: vi.fn().mockResolvedValue(undefined),
    deleteConnector: vi.fn().mockResolvedValue(undefined),
    refreshConnectors: vi.fn().mockResolvedValue(undefined),
    refreshPresets: vi.fn().mockResolvedValue(undefined),
    refreshCapabilities: vi.fn().mockResolvedValue(undefined),
    capabilities: [],
    toasts: [],
    pushToast: vi.fn(),
    dismissToast: vi.fn(),
  } as unknown as StudioContextValue;
}

describe("DiagnosticsModal", () => {
  beforeEach(() => {
    modalProps.onClose.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the exact bytes, size, and inclusion boundaries before export", () => {
    render(<DiagnosticsModal {...modalProps} />);

    expect(screen.getByRole("dialog", { name: "Review diagnostics" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Exact diagnostics JSON preview" }).textContent).toBe(modalProps.json);
    expect(screen.getByText(/16 bytes/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Included" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Never included" })).toBeInTheDocument();
    expect(screen.getByText(/sidecar is unavailable/i)).toBeInTheDocument();
  });

  it("traps keyboard focus and closes on Escape", () => {
    render(<DiagnosticsModal {...modalProps} />);

    const dialog = screen.getByRole("dialog");
    const close = screen.getByRole("button", { name: "Cancel diagnostics export" });
    const save = screen.getByRole("button", { name: "Save .json" });
    expect(close).toHaveFocus();
    save.focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(modalProps.onClose).toHaveBeenCalledOnce();
  });

  it("creates a local JSON download only when Save is pressed", () => {
    const create = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:diagnostics");
    const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<DiagnosticsModal {...modalProps} />);

    expect(create).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Save .json" }));

    expect(create).toHaveBeenCalledOnce();
    expect(revoke).toHaveBeenCalledWith("blob:diagnostics");
    expect(click).toHaveBeenCalledOnce();
  });

  it("still prepares a local bundle when the sidecar is unavailable", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        calls.push(String(input));
        throw new TypeError("Failed to fetch");
      }),
    );
    vi.mocked(useStudio).mockReturnValue(stubContext());
    render(
      <UpdateProvider service={service}>
        <OnboardingProvider enabled={false}>
          <SettingsPanel />
        </OnboardingProvider>
      </UpdateProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Create diagnostics bundle" }));

    expect(await screen.findByRole("dialog", { name: "Review diagnostics" })).toBeInTheDocument();
    expect(calls).toEqual(["/api/diagnostics"]);
    expect(screen.getByText(/sidecar is unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Exact diagnostics JSON preview" })).toHaveTextContent('"engine": null');
    expect(calls.every((url) => url.startsWith("/api/"))).toBe(true);
  });

  it("does not request diagnostics before consent and requests only local sidecar metadata after", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        calls.push(url);
        if (url === "/api/diagnostics") {
          return Response.json({
            version: "0.14.0",
            python: "3.12.4",
            db: { name: "odi.db", size_bytes: 0, integrity: "unknown", counts: {} },
            migrations: { events: "current" },
            capabilities: [],
          });
        }
        return new Response("Not found", { status: 404 });
      }),
    );
    vi.mocked(useStudio).mockReturnValue(stubContext());
    render(
      <UpdateProvider service={service}>
        <OnboardingProvider enabled={false}>
          <SettingsPanel />
        </OnboardingProvider>
      </UpdateProvider>,
    );

    expect(calls).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: "Create diagnostics bundle" }));

    expect(await screen.findByRole("dialog", { name: "Review diagnostics" })).toBeInTheDocument();
    await waitFor(() => expect(calls).toEqual(["/api/diagnostics"]));
    expect(calls.every((url) => url.startsWith("/api/"))).toBe(true);
    expect(screen.getByRole("region", { name: "Exact diagnostics JSON preview" })).not.toHaveTextContent("local-secret");
  });
});
