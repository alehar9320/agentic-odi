import { createRef } from "react";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StudioContextValue } from "../../state/StudioContext";
import { Composer } from "./Composer";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));
vi.mock("../../lib/commands", () => ({
  isCommandDraft: () => false,
  isSlashCommand: () => false,
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
    conversationId: null,
    conversations: [],
    conversationsLoading: false,
    openConversation: vi.fn(),
    deleteConversation: vi.fn(),
    renameConversation: vi.fn(),
    refreshConversations: vi.fn(),
    deleteMessage: vi.fn(),
    clearChat: vi.fn(),
    pushToast: vi.fn(),
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

    const chip = screen.getByRole("button", { name: /added gong, dismiss/i });
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent("Added Gong");
    fireEvent.click(chip);
    expect(dismiss).toHaveBeenCalledWith("gong");
    expect(refresh).toHaveBeenCalled();
  });

  it("renders nothing when there are no suggestions", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectorSuggestions: [] }));

    render(<Composer {...baseProps} />);

    expect(screen.queryByRole("button", { name: /added gong, dismiss/i })).not.toBeInTheDocument();
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

async function renderThreadComposer(overrides: Record<string, unknown> = {}) {
  const { StudioRuntimeProvider } = await import("../../assistant/StudioRuntime");
  const { ThreadComposer } = await import("./ThreadComposer");
  // The stub is handed back so a test can settle the run: the runtime reads
  // `streaming` again on the next render, and a copy of the value would not move.
  const studio = stubContext({
    connectorSuggestions: [],
    messages: [],
    streaming: false,
    canvas: null,
    pushToast: vi.fn(),
    sendMessage: vi.fn(async () => {}),
    regenerateFrom: vi.fn(async () => {}),
    editFrom: vi.fn(async () => {}),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(async () => {}),
    stopStreaming: vi.fn(),
    ...overrides,
  }) as unknown as Record<string, unknown>;
  vi.mocked(useStudio).mockReturnValue(studio as unknown as StudioContextValue);
  return {
    ...render(
      <StudioRuntimeProvider>
        <ThreadComposer onCommand={() => {}} />
      </StudioRuntimeProvider>,
    ),
    studio,
  };
}

describe("ThreadComposer attachments", () => {
  it("turns a dropped file into a removable attachment chip", async () => {
    const { container } = await renderThreadComposer();
    const root = container.querySelector(".composer") as HTMLElement;
    const file = new File(["hello"], "notes.md", { type: "text/markdown" });

    fireEvent.dragEnter(root, { dataTransfer: { types: ["Files"], files: [file] } });
    expect(screen.getByText("Drop to attach")).toBeInTheDocument();

    fireEvent.drop(root, { dataTransfer: { types: ["Files"], files: [file] } });

    expect(await screen.findByText("notes.md")).toBeInTheDocument();
    expect(screen.queryByText("Drop to attach")).toBeNull();
    expect(screen.getByRole("button", { name: "Remove notes.md" })).toBeInTheDocument();
  });

  it("refuses a file the studio cannot read and says why", async () => {
    const pushToast = vi.fn();
    const { container } = await renderThreadComposer({ pushToast });
    const root = container.querySelector(".composer") as HTMLElement;
    const file = new File(["x"], "deck.pdf", { type: "application/pdf" });

    fireEvent.drop(root, { dataTransfer: { types: ["Files"], files: [file] } });

    expect(pushToast).toHaveBeenCalledWith("error", expect.stringContaining("deck.pdf"));
    expect(screen.queryByText("deck.pdf")).toBeNull();
  });

  it("attaches a pasted screenshot from the clipboard", async () => {
    await renderThreadComposer();
    const file = new File(["png"], "screenshot.png", { type: "image/png" });

    fireEvent.paste(screen.getByRole("textbox", { name: "Message the studio" }), {
      clipboardData: { files: [file] },
    });

    expect(await screen.findByText("screenshot.png")).toBeInTheDocument();
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

describe("ThreadComposer queue", () => {
  it("buffers a follow-up instead of dropping it while a reply streams", async () => {
    const sendMessage = vi.fn<(text: string, files?: unknown) => Promise<void>>(
      async () => {},
    );
    const { rerender, studio } = await renderThreadComposer({
      streaming: true,
      sendMessage,
    });
    const box = screen.getByRole("textbox", { name: "Message the studio" });

    fireEvent.change(box, { target: { value: "and then?" } });
    fireEvent.keyDown(box, { key: "Enter" });

    expect(await screen.findByText("Next")).toBeInTheDocument();
    expect(screen.getByText("and then?")).toBeInTheDocument();
    expect(sendMessage).not.toHaveBeenCalled();

    // The next turn runs on its own once the live one settles.
    const { StudioRuntimeProvider } = await import("../../assistant/StudioRuntime");
    const { ThreadComposer } = await import("./ThreadComposer");
    studio.streaming = false;
    rerender(
      <StudioRuntimeProvider>
        <ThreadComposer onCommand={() => {}} />
      </StudioRuntimeProvider>,
    );

    await waitFor(() => expect(sendMessage).toHaveBeenCalledTimes(1));
    expect(sendMessage.mock.calls[0][0]).toBe("and then?");
  });
});
