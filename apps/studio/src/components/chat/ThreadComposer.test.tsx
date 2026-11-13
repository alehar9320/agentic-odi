import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ATTACHMENT_READ_FAILURE, MAX_ATTACHMENT_CHARS, tooLargeMessage } from "../../assistant/attachments";
import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { StudioCommand } from "../../lib/commands";
import { focusableWithin } from "../../lib/useFocusTrap";
import type { StudioContextValue } from "../../state/StudioContext";
import type { ChatMessage } from "../../types";
import { ThreadComposer } from "./ThreadComposer";

vi.mock("../../state/StudioContext", () => ({ useStudio: vi.fn() }));

import { useStudio } from "../../state/StudioContext";

function context(messages: ChatMessage[], overrides: Record<string, unknown> = {}) {
  return {
    settings: { base_url: "", api_key: "", model_name: "test-model", mcp_url: "", display_name: "" },
    llmHealth: { healthy: true, message: "" },
    brief: null,
    canvas: null,
    connectorSuggestions: [],
    presets: [],
    dismissConnectorSuggestion: vi.fn(),
    refreshConnectors: vi.fn(async () => {}),
    messages,
    streaming: false,
    sendMessage: vi.fn(async () => {}),
    regenerateFrom: vi.fn(async () => {}),
    editFrom: vi.fn(async () => {}),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(async () => {}),
    stopStreaming: vi.fn(),
    pushToast: vi.fn(),
    saveSettings: vi.fn(async () => {}),
    openPanel: vi.fn(),
    ...overrides,
  } as unknown as StudioContextValue;
}

const history: ChatMessage[] = [
  { id: "u-1", parentId: null, role: "user", content: "The first question" },
  { id: "a-1", parentId: "u-1", role: "assistant", content: "An answer" },
  { id: "u-2", parentId: "a-1", role: "user", content: "The latest question" },
  { id: "a-2", parentId: "u-2", role: "assistant", content: "Another answer" },
];

function renderComposer(
  overrides: Record<string, unknown> = {},
  onCommand: (command: StudioCommand) => void = () => {},
) {
  vi.mocked(useStudio).mockReturnValue(context(history, overrides));
  render(
    <StudioRuntimeProvider>
      <ThreadComposer onCommand={onCommand} />
    </StudioRuntimeProvider>,
  );
  return screen.getByRole("textbox", { name: "Message the studio" }) as HTMLTextAreaElement;
}

/**
 * `fireEvent`'s `key` and `isComposing` init both land on the native event, so
 * this is the same event shape a real input method emits mid-composition.
 */
function composingKeyDown(
  input: HTMLTextAreaElement,
  init: { key: string; shiftKey?: boolean },
) {
  fireEvent.keyDown(input, { ...init, isComposing: true });
}

function recalls(): string[] {
  return screen
    .queryAllByRole("status")
    .map((node) => node.textContent ?? "")
    .filter((text) => text.startsWith("Recalled your last message"));
}

describe("ThreadComposer recall", () => {
  it("recalls the message sent last on an empty draft, and says so once", () => {
    const input = renderComposer();

    fireEvent.keyDown(input, { key: "ArrowUp" });

    expect(input.value).toBe("The latest question");
    expect(recalls()).toHaveLength(1);
    expect(recalls()[0]).toContain("The latest question");
  });

  it("walks further back, then forward, then restores the draft", () => {
    const input = renderComposer();

    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(input.value).toBe("The latest question");

    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(input.value).toBe("The first question");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input.value).toBe("The latest question");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input.value).toBe("");
  });

  it("leaves a draft untouched when the caret is inside it", () => {
    const input = renderComposer();

    fireEvent.change(input, { target: { value: "a thought in progress" } });
    input.setSelectionRange(5, 5);
    fireEvent.keyDown(input, { key: "ArrowUp" });

    expect(input.value).toBe("a thought in progress");
    expect(recalls()).toHaveLength(0);
  });

  it("never recalls assistant text", () => {
    const input = renderComposer();

    fireEvent.keyDown(input, { key: "ArrowUp" });

    expect(input.value).not.toContain("Another answer");
  });

  it("still sends on Enter", () => {
    const sendMessage = vi.fn(async () => {});
    const input = renderComposer({ sendMessage });

    fireEvent.change(input, { target: { value: "Send this" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(sendMessage).toHaveBeenCalledWith("Send this", expect.anything());
  });
});

describe("ThreadComposer during IME composition", () => {
  it("leaves a composing Enter to the input method", () => {
    const onCommand = vi.fn();
    const sendMessage = vi.fn(async () => {});
    const input = renderComposer({ sendMessage }, onCommand);

    fireEvent.change(input, { target: { value: "/" } });
    composingKeyDown(input, { key: "Enter" });

    expect(onCommand).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(input.value).toBe("/");
  });

  it("treats the legacy keyCode 229 as composition too", () => {
    const onCommand = vi.fn();
    const sendMessage = vi.fn(async () => {});
    const input = renderComposer({ sendMessage }, onCommand);

    fireEvent.change(input, { target: { value: "/" } });
    // WebKit can commit a candidate with `isComposing` unset and keyCode 229.
    fireEvent.keyDown(input, { key: "Enter", keyCode: 229 });

    expect(onCommand).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(input.value).toBe("/");
  });

  it("does not move the palette highlight on a composing arrow", () => {
    const input = renderComposer();

    fireEvent.change(input, { target: { value: "/" } });
    composingKeyDown(input, { key: "ArrowDown" });

    expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true");
  });

  it("does not dismiss the palette on a composing Escape", () => {
    const input = renderComposer();

    fireEvent.change(input, { target: { value: "/" } });
    composingKeyDown(input, { key: "Escape" });

    expect(screen.getByRole("listbox", { name: "Commands" })).toBeInTheDocument();
  });

  it("does not recall history on a composing arrow", () => {
    const input = renderComposer();

    composingKeyDown(input, { key: "ArrowUp" });

    expect(input.value).toBe("");
    expect(recalls()).toHaveLength(0);
  });

  it("runs the highlighted command on a plain Enter once composition ends", () => {
    const onCommand = vi.fn();
    const input = renderComposer({}, onCommand);

    fireEvent.change(input, { target: { value: "/status" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onCommand).toHaveBeenCalledWith(expect.objectContaining({ id: "status" }));
  });

  it("moves the highlight and closes on plain arrows and Escape", () => {
    const input = renderComposer();

    fireEvent.change(input, { target: { value: "/" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("keeps Shift+Enter a newline and still sends a plain Enter", () => {
    const sendMessage = vi.fn(async () => {});
    const input = renderComposer({ sendMessage });

    fireEvent.change(input, { target: { value: "Send this" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
    expect(sendMessage).not.toHaveBeenCalled();

    fireEvent.keyDown(input, { key: "Enter" });
    expect(sendMessage).toHaveBeenCalledWith("Send this", expect.anything());
  });
});

describe("ThreadComposer focus chip", () => {
  const statement = "Reduce the time to reconcile a failed payment";
  const focusedSubject = { kind: "outcome", id: "O-9" };

  function withFocus(overrides: Record<string, unknown> = {}) {
    renderComposer({ focusedSubject, focusedSubjectLabel: statement, ...overrides });
  }

  it("admits which record the agent was told about", () => {
    withFocus();

    expect(screen.getByRole("button", { name: `Looking at: ${statement}` })).toBeTruthy();
  });

  it("announces the focus to a screen reader", () => {
    withFocus();

    const announced = screen
      .getAllByRole("status")
      .some((region) => (region.textContent ?? "").includes(statement));
    expect(announced).toBe(true);
  });

  it("says nothing when the screen has selected nothing", () => {
    renderComposer();

    expect(screen.queryByRole("button", { name: /Looking at/ })).toBeNull();
  });

  it("says nothing about a selection the canvas cannot name", () => {
    renderComposer({ focusedSubject, focusedSubjectLabel: null });

    expect(screen.queryByRole("button", { name: /Looking at/ })).toBeNull();
  });

  it("takes the person to the record when they press the chip", () => {
    const revealFocusedSubject = vi.fn();
    withFocus({ revealFocusedSubject });

    fireEvent.click(screen.getByRole("button", { name: `Looking at: ${statement}` }));

    expect(revealFocusedSubject).toHaveBeenCalledOnce();
  });

  it("stops speaking for the screen when the person clears it", () => {
    const clearFocus = vi.fn();
    withFocus({ clearFocus });

    fireEvent.click(
      screen.getByRole("button", { name: "Stop telling the agent what you are looking at" }),
    );

    expect(clearFocus).toHaveBeenCalledOnce();
  });
});

describe("ThreadComposer mixed clipboard paste", () => {
  const draft = "first line\nsecond line";

  /**
   * jsdom performs no clipboard default action, so the test supplies the one a
   * browser would: when the composer leaves the paste unprevented, the text is
   * inserted at the caret and the input event the app listens for is fired.
   */
  function paste(
    input: HTMLTextAreaElement,
    { text, files }: { text?: string; files?: File[] },
  ): boolean {
    const clipboardData = {
      files: files ?? [],
      getData: (type: string) => (type === "text/plain" ? (text ?? "") : ""),
    };
    const notPrevented = fireEvent.paste(input, { clipboardData });
    if (notPrevented && text) {
      const start = input.selectionStart ?? input.value.length;
      const end = input.selectionEnd ?? start;
      const next = input.value.slice(0, start) + text + input.value.slice(end);
      fireEvent.change(input, { target: { value: next } });
    }
    return notPrevented;
  }

  it("keeps the pasted text when the clipboard also carries an image", async () => {
    const sendMessage = vi.fn(async () => {});
    const input = renderComposer({ sendMessage });
    fireEvent.change(input, { target: { value: draft } });
    input.setSelectionRange(10, 10);
    const image = new File(["png"], "screenshot.png", { type: "image/png" });

    const notPrevented = paste(input, { text: "inserted", files: [image] });

    expect(notPrevented).toBe(true);
    expect(input.value).toBe("first lineinserted\nsecond line");
    expect(await screen.findByText("screenshot.png")).toBeInTheDocument();
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("inserts text-only paste once and attaches nothing", () => {
    const input = renderComposer();
    fireEvent.change(input, { target: { value: draft } });
    input.setSelectionRange(10, 10);

    paste(input, { text: "inserted" });

    expect(input.value).toBe("first lineinserted\nsecond line");
    expect(screen.queryByRole("listitem")).toBeNull();
  });

  it("attaches an image-only paste and inserts no text", async () => {
    const input = renderComposer();
    fireEvent.change(input, { target: { value: draft } });
    input.setSelectionRange(10, 10);
    const image = new File(["png"], "screenshot.png", { type: "image/png" });

    const notPrevented = paste(input, { files: [image] });

    expect(notPrevented).toBe(false);
    expect(input.value).toBe(draft);
    expect(await screen.findByText("screenshot.png")).toBeInTheDocument();
  });

  it("keeps the text and still names a refused file", () => {
    const pushToast = vi.fn();
    const input = renderComposer({ pushToast });
    fireEvent.change(input, { target: { value: draft } });
    input.setSelectionRange(10, 10);
    const pdf = new File(["x"], "deck.pdf", { type: "application/pdf" });

    paste(input, { text: "inserted", files: [pdf] });

    expect(input.value).toBe("first lineinserted\nsecond line");
    expect(pushToast).toHaveBeenCalledWith("error", expect.stringContaining("deck.pdf"));
    expect(screen.queryByText("deck.pdf")).toBeNull();
  });

  it("inserts multiline unicode text verbatim", () => {
    const input = renderComposer();
    fireEvent.change(input, { target: { value: "α β" } });
    input.setSelectionRange(3, 3);

    paste(input, { text: "héllo\nwörld" });

    expect(input.value).toBe("α βhéllo\nwörld");
  });

  it("never sends the turn from a paste", () => {
    const sendMessage = vi.fn(async () => {});
    const input = renderComposer({ sendMessage });
    const image = new File(["png"], "screenshot.png", { type: "image/png" });

    paste(input, { text: "inserted", files: [image] });

    expect(sendMessage).not.toHaveBeenCalled();
  });
});

/**
 * A file the browser hands over by name but gives nothing back for: a locked
 * transcript, a disk hiccup, a tab that lost the handle.
 */
function unreadableFile(name: string): File {
  const file = new File(["x"], name, { type: "text/markdown" });
  Object.defineProperty(file, "text", {
    value: () => Promise.reject(new Error("Read interrupted")),
  });
  return file;
}

function readableFile(name: string): File {
  return new File(["a thought worth sending"], name, { type: "text/markdown" });
}

function composerWithFiles(overrides: Record<string, unknown> = {}) {
  vi.mocked(useStudio).mockReturnValue(context([], overrides));
  const { container } = render(
    <StudioRuntimeProvider>
      <ThreadComposer onCommand={() => {}} />
    </StudioRuntimeProvider>,
  );
  return {
    root: container.querySelector(".composer") as HTMLElement,
    input: screen.getByRole("textbox", { name: "Message the studio" }) as HTMLTextAreaElement,
  };
}

function dropFiles(root: HTMLElement, files: File[]) {
  fireEvent.dragEnter(root, { dataTransfer: { types: ["Files"], files } });
  fireEvent.drop(root, { dataTransfer: { types: ["Files"], files } });
}

describe("ThreadComposer unreadable attachments", () => {
  it("names the file and says it could not be read", async () => {
    const { root } = composerWithFiles();

    dropFiles(root, [unreadableFile("notes.md")]);

    const failure = await screen.findByText(ATTACHMENT_READ_FAILURE);
    expect(failure.closest(".attachment-chip")).toHaveTextContent("notes.md");
  });

  it("keeps the draft and the readable file beside a failed one", async () => {
    const { root, input } = composerWithFiles();
    fireEvent.change(input, { target: { value: "a draft in progress" } });

    dropFiles(root, [readableFile("good.md"), unreadableFile("notes.md")]);
    await screen.findByText(ATTACHMENT_READ_FAILURE);

    expect(screen.getByText("good.md")).toBeInTheDocument();
    expect(input.value).toBe("a draft in progress");
  });

  it("leaves the failed chip on the tab path so it can be removed", async () => {
    const { root } = composerWithFiles();

    dropFiles(root, [unreadableFile("notes.md")]);

    const remove = await screen.findByRole("button", { name: "Remove notes.md" });
    expect(focusableWithin(root)).toContain(remove);

    fireEvent.click(remove);

    await waitFor(() => expect(screen.queryByText(ATTACHMENT_READ_FAILURE)).toBeNull());
  });

  it("holds the turn back while a file could not be read", async () => {
    const sendMessage = vi.fn(async () => {});
    const { root, input } = composerWithFiles({ sendMessage });

    dropFiles(root, [readableFile("good.md"), unreadableFile("notes.md")]);
    await screen.findByText(ATTACHMENT_READ_FAILURE);

    fireEvent.change(input, { target: { value: "Read these" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(sendMessage).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });

  it("sends once the failed file is gone, and with only the readable one", async () => {
    const sendMessage = vi.fn(async () => {});
    const { root, input } = composerWithFiles({ sendMessage });

    dropFiles(root, [readableFile("good.md"), unreadableFile("notes.md")]);
    await screen.findByText(ATTACHMENT_READ_FAILURE);

    fireEvent.click(screen.getByRole("button", { name: "Remove notes.md" }));
    await waitFor(() => expect(screen.queryByText(ATTACHMENT_READ_FAILURE)).toBeNull());

    fireEvent.change(input, { target: { value: "Read these" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(sendMessage).toHaveBeenCalledTimes(1));
    const [text, attachments] = sendMessage.mock.calls[0] as unknown as [
      string,
      { name: string }[],
    ];
    expect(text).toBe("Read these");
    expect(attachments.map((attachment) => attachment.name)).toEqual(["good.md"]);
  });
});

/**
 * A text file long enough to exceed the per-file character cap, so the adapter
 * refuses it instead of quietly shortening what the model would receive.
 */
function oversizedFile(name: string): File {
  return new File(["a".repeat(MAX_ATTACHMENT_CHARS + 5)], name, { type: "text/markdown" });
}

describe("ThreadComposer oversized attachments", () => {
  it("names the file and the limit on the chip instead of pretending it was sent", async () => {
    const { root } = composerWithFiles();

    dropFiles(root, [oversizedFile("interview.md")]);

    const failure = await screen.findByText(tooLargeMessage("interview.md"));
    const chip = failure.closest(".attachment-chip");
    expect(chip).toHaveTextContent("interview.md");
    expect(chip).toHaveTextContent("20,000");
  });

  it("keeps the draft and the readable file beside an oversized one", async () => {
    const { root, input } = composerWithFiles();
    fireEvent.change(input, { target: { value: "a draft in progress" } });

    dropFiles(root, [readableFile("good.md"), oversizedFile("interview.md")]);
    await screen.findByText(tooLargeMessage("interview.md"));

    expect(screen.getByText("good.md")).toBeInTheDocument();
    expect(input.value).toBe("a draft in progress");
  });

  it("leaves the chip reachable by keyboard and lets the remove control clear it", async () => {
    const { root } = composerWithFiles();

    dropFiles(root, [oversizedFile("interview.md")]);

    const remove = await screen.findByRole("button", { name: "Remove interview.md" });
    expect(focusableWithin(root)).toContain(remove);

    fireEvent.click(remove);

    await waitFor(() => expect(screen.queryByText(tooLargeMessage("interview.md"))).toBeNull());
  });

  it("holds the turn back while an oversized file is attached", async () => {
    const sendMessage = vi.fn(async () => {});
    const { root, input } = composerWithFiles({ sendMessage });

    dropFiles(root, [oversizedFile("interview.md")]);
    await screen.findByText(tooLargeMessage("interview.md"));

    fireEvent.change(input, { target: { value: "Read this" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(sendMessage).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });
});

const mentionCanvas = {
  jobs: [{ id: "J-1", name: "Reconcile a payment" }],
  steps: [{ id: "S-1", job_id: "J-1", name: "Find the failure" }],
  outcomes: [{ id: "O-1", job_id: "J-1", statement: "Minimize the time to reconcile" }],
  evidence: [{ id: "E-1", name: "Grain call", source_name: "Grain" }],
  source: "mcp" as const,
};

function mentionComposer(overrides: Record<string, unknown> = {}) {
  vi.mocked(useStudio).mockReturnValue(context([], { canvas: mentionCanvas, ...overrides }));
  render(
    <StudioRuntimeProvider>
      <ThreadComposer onCommand={() => {}} />
    </StudioRuntimeProvider>,
  );
  return screen.getByRole("textbox", { name: "Message the studio" }) as HTMLTextAreaElement;
}

describe("ThreadComposer @ mentions", () => {
  it("names the canvas records when @ is typed", async () => {
    const input = mentionComposer();

    fireEvent.change(input, { target: { value: "@" } });

    expect(await screen.findByRole("listbox", { name: "Records" })).toBeInTheDocument();
    const labels = screen.getAllByRole("option").map((node) => node.textContent ?? "");
    expect(labels.some((text) => text.includes("Reconcile a payment"))).toBe(true);
    expect(labels.some((text) => text.includes("Grain call"))).toBe(true);
  });

  it("inserts the record's own id, not its statement", async () => {
    const input = mentionComposer();

    fireEvent.change(input, { target: { value: "@minimize" } });
    const option = await screen.findByRole("option", { name: /Minimize the time to reconcile/ });
    fireEvent.click(option);

    await waitFor(() => expect(input.value).toContain("@O-1"));
    expect(input.value).not.toContain("Minimize the time to reconcile");
  });

  it("offers nothing to name when the canvas is empty", async () => {
    const input = mentionComposer({ canvas: null });

    fireEvent.change(input, { target: { value: "@" } });

    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });

  it("sends an unknown @word as typed rather than inventing a record", async () => {
    const sendMessage = vi.fn(async () => {});
    const input = mentionComposer({ sendMessage });

    fireEvent.change(input, { target: { value: "@nobody please look" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(sendMessage).toHaveBeenCalledWith("@nobody please look", expect.anything());
  });

  it("leaves @ inside a word alone", async () => {
    const input = mentionComposer();

    fireEvent.change(input, { target: { value: "user@example.com" } });

    expect(screen.queryByRole("listbox", { name: "Records" })).not.toBeInTheDocument();
  });

  it("closes on Escape without sending", async () => {
    const sendMessage = vi.fn(async () => {});
    const input = mentionComposer({ sendMessage });

    fireEvent.change(input, { target: { value: "@" } });
    await screen.findByRole("listbox", { name: "Records" });
    fireEvent.keyDown(input, { key: "Escape" });

    await waitFor(() =>
      expect(screen.queryByRole("listbox", { name: "Records" })).not.toBeInTheDocument(),
    );
    expect(sendMessage).not.toHaveBeenCalled();
  });
});
