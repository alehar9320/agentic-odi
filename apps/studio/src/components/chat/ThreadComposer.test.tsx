import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
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

function renderComposer(overrides: Record<string, unknown> = {}) {
  vi.mocked(useStudio).mockReturnValue(context(history, overrides));
  render(
    <StudioRuntimeProvider>
      <ThreadComposer onCommand={() => {}} />
    </StudioRuntimeProvider>,
  );
  return screen.getByRole("textbox", { name: "Message the studio" }) as HTMLTextAreaElement;
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

  it("keeps pasted text when clipboard also contains an image", () => {
    const input = renderComposer();
    fireEvent.change(input, { target: { value: "first line\nsecond line" } });
    input.setSelectionRange(10, 10);

    const file = new File(["png"], "screenshot.png", { type: "image/png" });
    const pasteEvent = {
      clipboardData: {
        files: [file],
        getData: (type: string) => (type === "text/plain" ? "inserted" : ""),
      },
      preventDefault: vi.fn(),
    } as unknown as ClipboardEvent;

    fireEvent.paste(input, pasteEvent);

    expect(input.value).toBe("first lineinserted\nsecond line");
    expect(pasteEvent.preventDefault).not.toHaveBeenCalled();
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
