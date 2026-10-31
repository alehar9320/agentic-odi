import { createRef } from "react";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StudioContextValue } from "../../state/StudioContext";
import { Composer } from "./Composer";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";

const stubContext = {
  settings: { base_url: "", api_key: "", model_name: "m", mcp_url: "" },
  llmHealth: { healthy: null, message: "" },
  brief: null,
  connectorSuggestions: [],
  presets: [],
  dismissConnectorSuggestion: vi.fn(),
  refreshConnectors: vi.fn().mockResolvedValue(undefined),
} as unknown as StudioContextValue;

const baseProps = {
  onChange: () => {},
  onSubmit: () => {},
  onCommand: () => {},
  streaming: false,
  onStop: () => {},
  inputRef: createRef<HTMLTextAreaElement>(),
};

describe("Composer command palette", () => {
  it("exposes commands as options in the labeled listbox", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext);

    render(<Composer {...baseProps} value="/" />);

    expect(screen.getByRole("listbox", { name: "Commands" })).toBeInTheDocument();
    expect(screen.getAllByRole("option").length).toBeGreaterThan(0);
  });

  it("narrows options to the typed match and runs it with Enter", () => {
    const onCommand = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext);
    const { rerender } = render(
      <Composer {...baseProps} value="/" onCommand={onCommand} />,
    );

    rerender(<Composer {...baseProps} value="/status" onCommand={onCommand} />);

    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(screen.getByRole("option")).toHaveTextContent("/status");
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    expect(onCommand).toHaveBeenCalledWith(expect.objectContaining({ id: "status" }));
  });
});
