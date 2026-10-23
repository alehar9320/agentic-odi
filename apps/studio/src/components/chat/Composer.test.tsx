import { createRef } from "react";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StudioContextValue } from "../../state/StudioContext";
import { Composer } from "./Composer";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));
vi.mock("../../lib/commands", () => ({
  isCommandDraft: () => false,
  matchCommands: () => [],
}));

import { useStudio } from "../../state/StudioContext";

const preset = {
  id: "gong",
  label: "Gong",
  area: "voice-of-customer" as const,
  summary: "",
  url: "",
  auth: "none" as const,
  env_vars: [],
  headers: {},
  docs: "",
  tools: [],
  is_recommended: false,
};

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    settings: { base_url: "", api_key: "", model_name: "m", mcp_url: "", display_name: "" },
    llmHealth: { healthy: null, message: "" },
    brief: null,
    connectorSuggestions: ["gong"],
    presets: [preset],
    dismissConnectorSuggestion: vi.fn(),
    refreshConnectors: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }) as unknown as StudioContextValue;

describe("Composer connector suggestions", () => {
  const baseProps = {
    value: "",
    onChange: () => {},
    onSubmit: () => {},
    onCommand: () => {},
    streaming: false,
    onStop: () => {},
    inputRef: createRef<HTMLTextAreaElement>(),
  };

  it("renders a dismissable chip per suggestion", () => {
    const dismiss = vi.fn();
    const refresh = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ dismissConnectorSuggestion: dismiss, refreshConnectors: refresh }),
    );

    render(<Composer {...baseProps} />);

    const chip = screen.getByRole("button", { name: /dismiss suggestion: gong/i });
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent("Suggested: Gong");
    fireEvent.click(chip);
    expect(dismiss).toHaveBeenCalledWith("gong");
    expect(refresh).toHaveBeenCalled();
  });

  it("renders nothing when there are no suggestions", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectorSuggestions: [] }));

    render(<Composer {...baseProps} />);

    expect(screen.queryByRole("button", { name: /suggested: gong/i })).not.toBeInTheDocument();
  });
});
