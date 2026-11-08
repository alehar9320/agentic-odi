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

  it("points the textbox at the highlighted option with aria-activedescendant", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext);
    render(<Composer {...baseProps} value="/" />);

    const textbox = screen.getByRole("textbox");
    const options = screen.getAllByRole("option");
    expect(options[0].id).not.toBe("");
    expect(textbox).toHaveAttribute("aria-activedescendant", options[0].id);

    fireEvent.keyDown(textbox, { key: "ArrowDown" });

    const highlighted = screen.getAllByRole("option")[1];
    expect(highlighted).toHaveAttribute("aria-selected", "true");
    expect(textbox).toHaveAttribute("aria-activedescendant", highlighted.id);
  });

  it("drops the active descendant when the palette closes", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext);
    const { rerender } = render(<Composer {...baseProps} value="/" />);

    expect(screen.getByRole("textbox")).toHaveAttribute("aria-activedescendant");

    rerender(<Composer {...baseProps} value="plain text" />);

    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.getByRole("textbox")).not.toHaveAttribute("aria-activedescendant");
  });

  it("keeps the highlighted command in view without moving the list further than it must", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext);
    const scroll = vi.fn();
    const original = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scroll;
    try {
      render(<Composer {...baseProps} value="/" />);
      const textbox = screen.getByRole("textbox");
      scroll.mockClear();

      for (let index = 0; index < 14; index += 1) {
        fireEvent.keyDown(textbox, { key: "ArrowDown" });
      }

      const last = scroll.mock.calls.at(-1)?.[0];
      expect(last).toMatchObject({ block: "nearest" });
      expect(last).toMatchObject({ behavior: "smooth" });
    } finally {
      Element.prototype.scrollIntoView = original;
    }
  });

  it("scrolls instantly when the person asks for less motion", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext);
    const scroll = vi.fn();
    const originalScroll = Element.prototype.scrollIntoView;
    const originalMatchMedia = window.matchMedia;
    Element.prototype.scrollIntoView = scroll;
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: (query: string) => ({
        matches: query.includes("prefers-reduced-motion"),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }),
    });
    try {
      render(<Composer {...baseProps} value="/" />);
      const textbox = screen.getByRole("textbox");
      scroll.mockClear();

      fireEvent.keyDown(textbox, { key: "ArrowDown" });

      expect(scroll.mock.calls.at(-1)?.[0]).toMatchObject({
        block: "nearest",
        behavior: "auto",
      });
    } finally {
      Element.prototype.scrollIntoView = originalScroll;
      Object.defineProperty(window, "matchMedia", {
        configurable: true,
        value: originalMatchMedia,
      });
    }
  });

  it("reaches the records lens by typing its name", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext);
    const onCommand = vi.fn();

    render(<Composer {...baseProps} value="/rec" onCommand={onCommand} />);

    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(screen.getByRole("option")).toHaveTextContent("/records");

    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

    expect(onCommand).toHaveBeenCalledWith(expect.objectContaining({ id: "records" }));
  });
});
