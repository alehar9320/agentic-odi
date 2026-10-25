import { createRef } from "react";

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { StudioContextValue } from "../../state/StudioContext";
import { Composer } from "./Composer";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
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

    const chip = screen.getByRole("button", { name: /added gong/i });
    expect(chip).toBeInTheDocument();
    fireEvent.click(chip);
    expect(dismiss).toHaveBeenCalledWith("gong");
    expect(refresh).toHaveBeenCalled();
  });

  it("renders nothing when there are no suggestions", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectorSuggestions: [] }));

    render(<Composer {...baseProps} />);

    expect(screen.queryByRole("button", { name: /added gong/i })).not.toBeInTheDocument();
  });
});

describe("Composer accessibility", () => {
  const baseProps = {
    onChange: () => {},
    onSubmit: () => {},
    onCommand: () => {},
    streaming: false,
    onStop: () => {},
    inputRef: createRef<HTMLTextAreaElement>(),
  };

  beforeEach(() => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectorSuggestions: [] }));
  });

  it("describes the field with the shortcut hint", () => {
    render(<Composer {...baseProps} value="" />);

    const input = screen.getByLabelText("Message the studio");
    const hint = document.getElementById(input.getAttribute("aria-describedby") ?? "");
    expect(hint).not.toBeNull();
    expect(hint?.textContent).toContain("to send");
  });

  it("points the field at the highlighted command while the palette is open", () => {
    render(<Composer {...baseProps} value="/" />);

    const input = screen.getByLabelText("Message the studio");
    expect(input).toHaveAttribute("aria-activedescendant", "studio-command-help");
    expect(document.getElementById("studio-command-help")).not.toBeNull();

    fireEvent.keyDown(input, { key: "ArrowDown" });

    expect(input).toHaveAttribute("aria-activedescendant", "studio-command-start");
    expect(document.getElementById("studio-command-start")).not.toBeNull();
  });

  it("stops a streaming reply with Escape and shows the shortcut", () => {
    const onStop = vi.fn();
    render(<Composer {...baseProps} value="" streaming onStop={onStop} />);

    expect(screen.getByText(/to stop/i)).toBeInTheDocument();

    fireEvent.keyDown(screen.getByLabelText("Message the studio"), { key: "Escape" });

    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it("does not stop anything when no reply is streaming", () => {
    const onStop = vi.fn();
    render(<Composer {...baseProps} value="" onStop={onStop} />);

    fireEvent.keyDown(screen.getByLabelText("Message the studio"), { key: "Escape" });

    expect(onStop).not.toHaveBeenCalled();
  });
});
