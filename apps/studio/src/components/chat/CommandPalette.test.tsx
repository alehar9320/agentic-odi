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
  it("groups every command under its category", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext);

    render(<Composer {...baseProps} value="/" />);

    expect(screen.getByRole("group", { name: "Start" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Explore" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Act" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Studio" })).toBeInTheDocument();
  });

  it("narrows the groups to the typed match and runs it with Enter", () => {
    const onCommand = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext);
    const { rerender } = render(
      <Composer {...baseProps} value="/" onCommand={onCommand} />,
    );

    rerender(<Composer {...baseProps} value="/status" onCommand={onCommand} />);

    expect(screen.queryByRole("group", { name: "Start" })).not.toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Studio" })).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    expect(onCommand).toHaveBeenCalledWith(expect.objectContaining({ id: "status" }));
  });
});
