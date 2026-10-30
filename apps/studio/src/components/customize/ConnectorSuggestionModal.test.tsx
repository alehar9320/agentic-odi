import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConnectorSuggestionModal } from "./ConnectorSuggestionModal";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio, type StudioContextValue } from "../../state/StudioContext";
import type { MarketplaceListing } from "../../types";

const LISTING: MarketplaceListing = {
  id: "io.github.acme/gong",
  name: "gong",
  title: "Gong",
  summary: "Call recordings and transcripts.",
  version: "1.0.0",
  url: "https://gong.example/mcp",
  source: "official",
  area: "voice-of-customer",
  repository: null,
  docs: null,
  env_vars: ["GONG_TOKEN"],
  headers: {},
  auth: "none",
  installable: true,
  verified: true,
  pull_count: 0,
  is_recommended: false,
  unavailable_reason: null,
  connector_name: "gong",
};

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    connectorSuggestion: null,
    dismissConnectorModal: vi.fn(),
    dismissConnectorSuggestion: vi.fn(),
    openCustomize: vi.fn(),
    installFromMarketplace: vi.fn().mockResolvedValue(true),
    ...overrides,
  }) as unknown as StudioContextValue;

describe("ConnectorSuggestionModal", () => {
  it("renders nothing when there is no suggestion", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    const { container } = render(<ConnectorSuggestionModal />);

    expect(container).toBeEmptyDOMElement();
  });

  it("offers the agent's suggestion and installs it", async () => {
    const install = vi.fn().mockResolvedValue(true);
    const dismiss = vi.fn();
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        connectorSuggestion: { id: "gong", listing: LISTING, reason: "agent" },
        installFromMarketplace: install,
        dismissConnectorSuggestion: dismiss,
      }),
    );

    render(<ConnectorSuggestionModal />);
    fireEvent.click(screen.getByRole("button", { name: "Add it" }));

    await waitFor(() => expect(install).toHaveBeenCalledWith(LISTING));
    expect(dismiss).toHaveBeenCalledWith("gong");
  });

  it("nudges a thin studio with its first pick", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        connectorSuggestion: { id: LISTING.id, listing: LISTING, reason: "empty" },
      }),
    );

    render(<ConnectorSuggestionModal />);

    expect(screen.getByText("Give the studio something to read")).toBeInTheDocument();
  });

  it("names the environment variable the connector needs", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        connectorSuggestion: { id: "gong", listing: LISTING, reason: "agent" },
      }),
    );

    render(<ConnectorSuggestionModal />);

    expect(screen.getByText("GONG_TOKEN")).toBeInTheDocument();
  });

  it("opens Customize on the Connectors tab and targets the suggested listing", () => {
    const openCustomize = vi.fn();
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        connectorSuggestion: { id: "gong", listing: LISTING, reason: "agent" },
        openCustomize,
      }),
    );

    render(<ConnectorSuggestionModal />);
    fireEvent.click(screen.getByRole("button", { name: "Browse all" }));

    expect(openCustomize).toHaveBeenCalledWith({
      query: "gong",
      listingId: LISTING.id,
      tab: "connectors",
    });
  });

  it("browses all when the suggestion has no listing to install", () => {
    const openCustomize = vi.fn();
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        connectorSuggestion: { id: "gong", listing: null, reason: "agent" },
        openCustomize,
      }),
    );

    render(<ConnectorSuggestionModal />);
    fireEvent.click(screen.getByRole("button", { name: "Browse all" }));

    expect(openCustomize).toHaveBeenCalledWith({ query: "gong", tab: "connectors" });
  });

  it("moves focus into the dialog and traps Tab at both ends", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        connectorSuggestion: { id: "gong", listing: LISTING, reason: "agent" },
      }),
    );

    render(<ConnectorSuggestionModal />);

    const dialog = screen.getByRole("dialog", { name: "Connector suggestion" });
    const close = screen.getByRole("button", { name: "Dismiss" });
    expect(close).toHaveFocus();

    const notNow = screen.getByRole("button", { name: "Not now" });
    notNow.focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(notNow).toHaveFocus();
  });

  it("dismisses for good when the user says not now", () => {
    const dismissSuggestion = vi.fn();
    const dismissModal = vi.fn();
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        connectorSuggestion: { id: "gong", listing: LISTING, reason: "agent" },
        dismissConnectorSuggestion: dismissSuggestion,
        dismissConnectorModal: dismissModal,
      }),
    );

    render(<ConnectorSuggestionModal />);
    fireEvent.click(screen.getByRole("button", { name: "Not now" }));

    expect(dismissSuggestion).toHaveBeenCalledWith("gong");
    expect(dismissModal).toHaveBeenCalled();
  });
});
