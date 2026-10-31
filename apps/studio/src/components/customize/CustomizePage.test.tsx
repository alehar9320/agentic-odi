import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CustomizePage } from "./CustomizePage";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio, type StudioContextValue } from "../../state/StudioContext";
import type { MarketplaceListing } from "../../types";

function listing(overrides: Partial<MarketplaceListing> = {}): MarketplaceListing {
  return {
    id: "io.github.acme/notion",
    name: "notion",
    title: "Notion",
    summary: "Read and write Notion pages.",
    version: "1.2.0",
    url: "https://notion.example/mcp",
    source: "official",
    area: "knowledge",
    repository: "https://github.com/acme/notion",
    docs: "https://docs.example/notion",
    env_vars: ["NOTION_TOKEN"],
    headers: {},
    auth: "oauth",
    installable: true,
    verified: true,
    pull_count: 24500,
    is_recommended: true,
    unavailable_reason: null,
    connector_name: "notion",
    ...overrides,
  };
}

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    settings: { base_url: "http://x", api_key: "k", model_name: "m", mcp_url: "u", theme: "dark" },
    saveSettings: vi.fn(),
    displayName: "Ada",
    setDisplayName: vi.fn(),
    brief: null,
    openSetup: vi.fn(),
    canvasState: { kind: "ready", data: { jobs: [], steps: [], outcomes: [], evidence: [], source: "local" } },
    models: [],
    modelsLoading: false,
    modelsMessage: null,
    refreshModels: vi.fn().mockResolvedValue(undefined),
    llmHealth: { healthy: true, message: "ok" },
    capabilities: [],
    mcpReachable: true,
    sidecarReachable: true,
    addConnector: vi.fn().mockResolvedValue(undefined),
    connectors: [],
    connectorsError: null,
    refreshConnectors: vi.fn().mockResolvedValue(undefined),
    deleteConnector: vi.fn().mockResolvedValue(undefined),
    closeCustomize: vi.fn(),
    customizeTarget: null,
    marketplace: {
      listings: [listing()],
      areas: { knowledge: "Knowledge" },
      cached: false,
      types: [
        { id: "mcp", label: "MCP servers", available: true },
        { id: "a2a", label: "A2A agents", available: false, note: "coming soon" },
      ],
    },
    marketplaceError: null,
    marketplaceLoading: false,
    searchMarketplace: vi.fn().mockResolvedValue(undefined),
    featured: [listing({ id: "preset-notion", source: "preset" })],
    featuredError: null,
    refreshFeatured: vi.fn().mockResolvedValue(undefined),
    installFromMarketplace: vi.fn().mockResolvedValue(true),
    ...overrides,
  }) as unknown as StudioContextValue;

describe("CustomizePage", () => {
  it("shows five named tabs with labelled panels and starts on Connectors", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    render(<CustomizePage />);

    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      "Model",
      "Appearance",
      "Data",
      "Connectors",
      "Shortcuts",
    ]);
    expect(screen.getByRole("tablist", { name: "Customize sections" })).toBeInTheDocument();
    for (const tab of tabs) {
      const id = tab.getAttribute("aria-controls");
      expect(id).toBeTruthy();
      const panel = document.getElementById(id!);
      expect(panel).toHaveAttribute("role", "tabpanel");
      expect(panel).toHaveAttribute("aria-labelledby", tab.id);
    }
    expect(screen.getByRole("tab", { name: "Connectors" })).toHaveAttribute("aria-selected", "true");
  });

  it("searches the marketplace only when Connectors is selected", async () => {
    const context = stubContext();
    vi.mocked(useStudio).mockReturnValue(context);

    render(<CustomizePage />);

    expect(context.refreshConnectors).toHaveBeenCalledOnce();
    expect(context.refreshFeatured).toHaveBeenCalledOnce();
    await waitFor(() => expect(context.searchMarketplace).toHaveBeenCalledWith({ q: "", area: "" }));
  });

  it.each([
    ["Model", "model", "Base URL"],
    ["Appearance", "appearance", "Your name"],
    ["Data", "data", "Your context"],
    ["Shortcuts", "shortcuts", "Shift + Enter"],
  ])("keeps the %s section local and issues no discovery requests", async (tabName, tabId, content) => {
    const context = stubContext({ customizeTarget: { tab: tabId } });
    vi.mocked(useStudio).mockReturnValue(context);

    render(<CustomizePage />);

    const panel = screen.getByRole("tabpanel", { name: tabName });
    expect(within(panel).getByText(content, { exact: false })).toBeInTheDocument();
    expect(context.refreshConnectors).not.toHaveBeenCalled();
    expect(context.refreshFeatured).not.toHaveBeenCalled();
    expect(context.searchMarketplace).not.toHaveBeenCalled();
  });

  it("moves tab focus and selection with arrow, Home, and End", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    render(<CustomizePage />);
    const connectors = screen.getByRole("tab", { name: "Connectors" });

    fireEvent.keyDown(connectors, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Shortcuts" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Shortcuts" })).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(screen.getByRole("tab", { name: "Shortcuts" }), { key: "Home" });
    expect(screen.getByRole("tab", { name: "Model" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Model" })).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(screen.getByRole("tab", { name: "Model" }), { key: "ArrowLeft" });
    expect(screen.getByRole("tab", { name: "Shortcuts" })).toHaveFocus();

    fireEvent.keyDown(screen.getByRole("tab", { name: "Shortcuts" }), { key: "End" });
    expect(screen.getByRole("tab", { name: "Shortcuts" })).toHaveFocus();
  });

  it("debounces typing instead of firing a request per keystroke", async () => {
    vi.useFakeTimers();
    const search = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useStudio).mockReturnValue(stubContext({ searchMarketplace: search }));

    render(<CustomizePage />);
    const input = screen.getByLabelText("Search the marketplace");
    for (const value of ["l", "li", "lin"]) {
      fireEvent.change(input, { target: { value } });
    }

    expect(search).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(250);
    });
    expect(search).toHaveBeenCalledTimes(1);
    expect(search).toHaveBeenCalledWith({ q: "lin", area: "" });
    vi.useRealTimers();
  });

  it("opens on the query a suggestion sent it", async () => {
    const search = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ searchMarketplace: search, customizeTarget: { query: "notion", tab: "connectors" } }),
    );

    render(<CustomizePage />);

    expect(screen.getByLabelText("Search the marketplace")).toHaveValue("notion");
    await waitFor(() => expect(search).toHaveBeenCalledWith({ q: "notion", area: "" }));
  });

  it("filters by capability area", async () => {
    const search = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useStudio).mockReturnValue(stubContext({ searchMarketplace: search }));

    render(<CustomizePage />);
    fireEvent.click(screen.getByRole("button", { name: "Knowledge" }));

    await waitFor(() => expect(search).toHaveBeenLastCalledWith({ q: "", area: "knowledge" }));
  });

  it("installs a listing by its marketplace id", async () => {
    const install = vi.fn().mockResolvedValue(true);
    const pick = listing({ id: "preset-notion", source: "preset" });
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ installFromMarketplace: install, featured: [pick] }),
    );

    render(<CustomizePage />);
    const buttons = screen.getAllByRole("button", { name: "Add" });
    fireEvent.click(buttons[0]);

    await waitFor(() => expect(install).toHaveBeenCalledWith(pick));
  });

  it("provides a manual connector form with connectors loaded from one shared context snapshot", () => {
    const refreshConnectors = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ connectors: [{ name: "notion", kind: "mcp", enabled: true }], refreshConnectors }),
    );

    render(<CustomizePage />);

    expect(screen.getByRole("list", { name: "Installed connectors" })).toHaveTextContent("notion");
    expect(screen.getByText("Add by URL")).toBeInTheDocument();
    expect(refreshConnectors).toHaveBeenCalledOnce();
  });

  it("shows an installed connector as added instead of installable", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ connectors: [{ name: "notion", kind: "mcp", enabled: true }] }),
    );

    render(<CustomizePage />);

    expect(screen.getAllByText("Added").length).toBeGreaterThan(0);
  });

  it("states the environment variable a listing needs", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    render(<CustomizePage />);

    expect(screen.getByText("NOTION_TOKEN")).toBeInTheDocument();
  });

  it("offers an unavailable connector type as an enabled filter, with the reason", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    render(<CustomizePage />);

    const a2a = screen.getByRole("button", { name: /A2A agents/ });
    expect(a2a).toBeEnabled();
    expect(a2a).toHaveTextContent("Coming soon");
    fireEvent.click(a2a);
    expect(screen.getByRole("region", { name: "A2A agents" })).toBeInTheDocument();
  });

  it("scopes offline connector failures to Connectors and provides a disabled manual form", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ sidecarReachable: false }));

    render(<CustomizePage />);

    const connectorsPanel = screen.getByRole("tabpanel", { name: "Connectors" });
    expect(within(connectorsPanel).getAllByRole("alert")).toHaveLength(1);
    expect(within(connectorsPanel).getByText("Connectors need the sidecar")).toBeInTheDocument();
    expect(within(connectorsPanel).getByLabelText("Connector name")).toBeDisabled();
    expect(within(connectorsPanel).getByLabelText("Connector URL")).toBeDisabled();
    expect(within(connectorsPanel).getByRole("button", { name: "Retry" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Model" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("allows adding a connector by URL when the marketplace is unavailable", async () => {
    const addConnector = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        addConnector,
        marketplace: null,
        marketplaceError: { message: "The marketplace is unreachable.", retryable: true },
      }),
    );

    render(<CustomizePage />);
    fireEvent.click(screen.getByText("Add by URL"));
    fireEvent.change(screen.getByLabelText("Connector name"), { target: { value: "gong" } });
    fireEvent.change(screen.getByLabelText("Connector URL"), { target: { value: "https://gong.example/mcp" } });
    fireEvent.click(screen.getByRole("button", { name: "Add connector" }));

    await waitFor(() => expect(addConnector).toHaveBeenCalledWith({ name: "gong", url: "https://gong.example/mcp" }));
  });

  it("explains an unreachable marketplace instead of showing nothing", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        marketplace: null,
        marketplaceError: { message: "The marketplace is unreachable.", retryable: true },
      }),
    );

    render(<CustomizePage />);

    expect(screen.getByRole("alert")).toHaveTextContent("The marketplace is unreachable.");
  });

  it("opens on the requested tab and query", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ customizeTarget: { tab: "model", query: "notion" } }),
    );

    render(<CustomizePage />);

    expect(screen.getByRole("tab", { name: "Model" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Model" })).toBeInTheDocument();
  });

  it("focuses and highlights a deep-linked listing", async () => {
    const target = listing({ id: "official:com.acme/notion", name: "com.acme/notion" });
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { value: scrollIntoView, configurable: true });
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        customizeTarget: { tab: "connectors", query: "notion", listingId: target.id },
        featured: [listing({ id: "preset-notion", source: "preset" })],
        marketplace: { listings: [target], areas: {}, cached: false, types: [] },
      }),
    );

    render(<CustomizePage />);
    const card = document.querySelector<HTMLElement>(".connector-card[aria-current='true']");
    expect(card).not.toBeNull();

    await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ block: "center" }));
    expect(card).toHaveClass("is-targeted");
    expect(card).toHaveFocus();
    delete (HTMLElement.prototype as Partial<HTMLElement>).scrollIntoView;
  });

  it("matches an installed connector whose registry name differs from its listing name", () => {
    // `com.acme/thing` installs as `thing`, so matching on the raw name would
    // leave an installed connector still offering "Add".
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        featured: [],
        connectors: [{ name: "thing", kind: "mcp", enabled: true }],
        marketplace: {
          listings: [
            listing({
              id: "official:com.acme/thing",
              name: "com.acme/thing",
              connector_name: "thing",
            }),
          ],
          areas: {},
          cached: false,
          types: [],
        },
      }),
    );

    render(<CustomizePage />);

    expect(screen.getByText("Added")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument();
  });

  it("says a listing cannot be installed and why", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        featured: [],
        marketplace: {
          listings: [
            listing({
              id: "io.github.acme/legacy",
              name: "legacy",
              connector_name: "legacy",
              installable: false,
              unavailable_reason: "Needs a local runtime",
            }),
          ],
          areas: {},
          cached: false,
          types: [],
        },
      }),
    );

    render(<CustomizePage />);

    expect(screen.getByText("Needs a local runtime")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument();
  });
});
