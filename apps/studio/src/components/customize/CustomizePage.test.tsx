import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  it("searches on open", async () => {
    const search = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useStudio).mockReturnValue(stubContext({ searchMarketplace: search }));

    render(<CustomizePage />);

    await waitFor(() => expect(search).toHaveBeenCalledWith({ q: "", area: "" }));
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
      stubContext({ searchMarketplace: search, customizeTarget: { query: "notion" } }),
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

  it("offers an unavailable connection type as disabled, with the reason", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    render(<CustomizePage />);

    const a2a = screen.getByRole("tab", { name: /A2A agents/ });
    expect(a2a).toBeDisabled();
    expect(a2a).toHaveTextContent("coming soon");
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
