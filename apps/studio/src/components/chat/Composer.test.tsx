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

describe("ThreadComposer attachment guidance", () => {
  it("describes supported files and the extraction limits on the attachment control", async () => {
    const { StudioRuntimeProvider } = await import("../../assistant/StudioRuntime");
    const { ThreadComposer } = await import("./ThreadComposer");
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        connectorSuggestions: [],
        messages: [],
        streaming: false,
        canvas: null,
        sendMessage: vi.fn(async () => {}),
        regenerateFrom: vi.fn(async () => {}),
        editFrom: vi.fn(async () => {}),
        switchBranch: vi.fn(),
        respondToApproval: vi.fn(async () => {}),
        stopStreaming: vi.fn(),
      }),
    );
    render(
      <StudioRuntimeProvider>
        <ThreadComposer onCommand={() => {}} />
      </StudioRuntimeProvider>,
    );

    const attachment = screen.getByRole("button", { name: "Attach a file" });
    expect(attachment).toHaveAccessibleDescription(/\.md.*\.json.*PNG.*JPEG.*WEBP.*GIF/i);
    expect(attachment).toHaveAccessibleDescription(/5 MB/);
    expect(attachment).toHaveAccessibleDescription(/20,000 characters/);
  });
});

describe("Composer keyboard focus", () => {
  const baseProps = {
    value: "hello",
    onChange: () => {},
    onSubmit: () => {},
    onCommand: () => {},
    streaming: false,
    onStop: () => {},
    inputRef: createRef<HTMLTextAreaElement>(),
  };

  it("keeps the send control in the tab order so it can take keyboard focus", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectorSuggestions: [] }));

    render(<Composer {...baseProps} />);
    const send = screen.getByRole("button", { name: "Send message" });
    send.focus();

    expect(send.tabIndex).toBe(0);
    expect(document.activeElement).toBe(send);
  });

  it("keeps the stop control focusable while a reply streams", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectorSuggestions: [] }));

    render(<Composer {...baseProps} streaming />);
    const stop = screen.getByRole("button", { name: "Stop generating" });
    stop.focus();

    expect(stop.tabIndex).toBe(0);
    expect(document.activeElement).toBe(stop);
  });
});
