import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingsPanel } from "./SettingsPanel";

vi.mock("../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));
vi.mock("./updater/useUpdater", () => ({
  useUpdater: () => ({
    checking: false,
    available: false,
    version: null,
    progress: null,
    error: null,
    check: vi.fn(),
  }),
}));

import { useStudio } from "../state/StudioContext";
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
    ...overrides,
  }) as unknown as StudioContextValue;

describe("SettingsPanel connectors", () => {
  it("renders registered connectors and removes one on click", () => {
    const del = vi.fn().mockResolvedValue({ ok: true, name: "notion" });
    vi.mocked(useStudio).mockReturnValue(stubContext({ deleteConnector: del }));

    render(<SettingsPanel />);

    expect(screen.getByText(/notion/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /remove notion/i }));
    expect(del).toHaveBeenCalledWith("notion");
  });

  it("adds a connector from a selected preset", () => {
    const add = vi.fn().mockResolvedValue({ ok: true, name: "notion" });
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ addConnector: add, connectors: [] }),
    );

    render(<SettingsPanel />);

    fireEvent.change(screen.getByRole("combobox", { name: /add preset/i }), {
      target: { value: "notion" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add preset/i }));
    expect(add).toHaveBeenCalledWith({ preset: "notion" });
  });

  it("shows an empty state when no connectors are registered", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectors: [] }));

    render(<SettingsPanel />);

    expect(screen.getByText(/no connectors registered/i)).toBeInTheDocument();
  });
});
