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

    const chip = screen.getByRole("button", { name: /hide gong/i });
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent("Added Gong");
    fireEvent.click(chip);
    expect(dismiss).toHaveBeenCalledWith("gong");
    expect(refresh).toHaveBeenCalled();
  });

  it("names a connection the store already holds as a state, not a toast (#698 D33)", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        connectors: [{ name: "gong", kind: "voice-of-customer", enabled: true }],
        connectorSuggestions: ["gong"],
      }),
    );

    render(<Composer {...baseProps} />);

    expect(screen.getByText("Connected to Gong")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /hide gong/i })).toBeInTheDocument();
  });


  it("renders nothing when there are no suggestions", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectorSuggestions: [] }));

    render(<Composer {...baseProps} />);

    expect(screen.queryByRole("button", { name: /added gong, dismiss/i })).not.toBeInTheDocument();
  });
});

describe("Composer keycap labels", () => {
  const baseProps = {
    value: "",
    onChange: () => {},
    onSubmit: () => {},
    onCommand: () => {},
    streaming: false,
    onStop: () => {},
    inputRef: createRef<HTMLTextAreaElement>(),
  };

  it.each([
    ["Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15", "⌘K", "↵"],
    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Ctrl K", "Enter"],
    ["Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36", "Ctrl K", "Enter"],
  ])("draws the keys this machine actually has (%s)", (userAgent, focus, send) => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ connectorSuggestions: [] }));
    const original = navigator.userAgent;
    Object.defineProperty(navigator, "userAgent", { value: userAgent, configurable: true });
    try {
      render(<Composer {...baseProps} />);

      const hint = document.querySelector(".composer__hint") as HTMLElement;
      const caps = Array.from(hint.querySelectorAll("kbd")).map((cap) => cap.textContent);
      expect(caps).toContain(focus);
      expect(caps).toContain(send);
    } finally {
      Object.defineProperty(navigator, "userAgent", { value: original, configurable: true });
    }
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
    expect(attachment).toHaveAccessibleDescription(/\.docx/i);
    expect(attachment).toHaveAccessibleDescription(/5 MB/);
    expect(attachment).toHaveAccessibleDescription(/20,000 characters/);
  });
});

async function renderThreadComposer(overrides: Record<string, unknown> = {}) {
  const { StudioRuntimeProvider } = await import("../../assistant/StudioRuntime");
  const { ThreadComposer } = await import("./ThreadComposer");
  vi.mocked(useStudio).mockReturnValue(
    stubContext({
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
    }),
  );
  return render(
    <StudioRuntimeProvider>
      <ThreadComposer onCommand={() => {}} />
    </StudioRuntimeProvider>,
  );
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

  it("accepts a dropped .docx as an attachment chip", async () => {
    const { container } = await renderThreadComposer();
    const root = container.querySelector(".composer") as HTMLElement;
    const file = new File(["x"], "brief.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    fireEvent.drop(root, { dataTransfer: { types: ["Files"], files: [file] } });

    expect(await screen.findByText("brief.docx")).toBeInTheDocument();
  });

  it("refuses a legacy .doc and names the reason", async () => {
    const pushToast = vi.fn();
    const { container } = await renderThreadComposer({ pushToast });
    const root = container.querySelector(".composer") as HTMLElement;
    const file = new File(["x"], "old.doc", { type: "application/msword" });

    fireEvent.drop(root, { dataTransfer: { types: ["Files"], files: [file] } });

    expect(pushToast).toHaveBeenCalledWith("error", expect.stringContaining("Save it as .docx or .txt first"));
    expect(screen.queryByText("old.doc")).toBeNull();
  });

  it("attaches a pasted screenshot from the clipboard", async () => {
    await renderThreadComposer();
    const file = new File(["png"], "screenshot.png", { type: "image/png" });

    fireEvent.paste(screen.getByRole("textbox", { name: "Message the studio" }), {
      clipboardData: { files: [file] },
    });

    expect(await screen.findByText("screenshot.png")).toBeInTheDocument();
  });

  it("keeps five mixed attachments and refuses the rest, naming the file and the limit", async () => {
    const pushToast = vi.fn();
    const { container } = await renderThreadComposer({ pushToast });
    const root = container.querySelector(".composer") as HTMLElement;
    const files = [1, 2, 3, 4, 5, 6].map(
      (n) => new File(["x"], `notes-${n}.txt`, { type: "text/plain" }),
    );
    fireEvent.drop(root, { dataTransfer: { types: ["Files"], files } });

    await screen.findByText("notes-1.txt");
    await screen.findByText("notes-5.txt");
    expect(screen.queryByText("notes-6.txt")).toBeNull();
    expect(await screen.findAllByRole("listitem")).toHaveLength(5);

    expect(pushToast).toHaveBeenCalledWith("error", expect.stringContaining("notes-6.txt"));
    expect(pushToast).toHaveBeenCalledWith("error", expect.stringContaining("5-file"));

    const refusal = screen.getByText(/exceeds the 5-file attachment limit/);
    expect(refusal).toHaveTextContent(/exceeds the 5-file attachment limit/);
    expect(refusal).toHaveTextContent(/notes-6.txt/);
  });

  it("shows the attachment counter as files are added and removed", async () => {
    const pushToast = vi.fn();
    const { container } = await renderThreadComposer({ pushToast });
    const root = container.querySelector(".composer") as HTMLElement;
    const file = (n: number) => new File(["x"], `notes-${n}.txt`, { type: "text/plain" });

    fireEvent.drop(root, { dataTransfer: { types: ["Files"], files: [file(1)] } });
    await screen.findByText("1 of 5 files");

    fireEvent.drop(root, {
      dataTransfer: { types: ["Files"], files: [file(2), file(3), file(4), file(5)] },
    });
    await screen.findByText("5 of 5 files");

    fireEvent.click(screen.getByRole("button", { name: "Remove notes-1.txt" }));
    await screen.findByText("4 of 5 files");

    // Making room admits one more and refuses the next.
    fireEvent.drop(root, { dataTransfer: { types: ["Files"], files: [file(6), file(7)] } });
    expect(pushToast).toHaveBeenCalledWith("error", expect.stringContaining("notes-7.txt"));
    await screen.findByText("5 of 5 files");
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
