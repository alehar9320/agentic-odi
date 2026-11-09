import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const speech = vi.hoisted(() => {
  const cancel = vi.fn();
  return {
    cancel,
    speak: vi.fn(() => ({
      status: { type: "running" as const },
      cancel,
      subscribe: () => () => {},
    })),
  };
});

vi.mock("../../assistant/speech", () => ({
  createSpeechAdapter: () => ({ speak: speech.speak }),
  speechSupported: () => true,
}));

import { ThreadPrimitive } from "@assistant-ui/react";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { ChatMessage } from "../../types";
import { Conversation } from "./Conversation";

const harness = vi.hoisted(() => ({
  state: {
    messages: [] as unknown[],
    streaming: false,
    thinkingPhase: null as string | null,
    toolActivity: [] as unknown[],
    offlineReply: false,
    canvas: null,
    regenerateFrom: vi.fn(),
    editFrom: vi.fn(),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(),
    stopStreaming: vi.fn(),
    sendMessage: vi.fn<(text: string) => Promise<void>>(),
  },
}));

vi.mock("../../state/StudioContext", () => ({ useStudio: () => harness.state }));

const turn: ChatMessage[] = [
  { id: "u-1", parentId: null, role: "user", content: "Check this bet" },
  { id: "a-1", parentId: "u-1", role: "assistant", content: "Listen to this answer." },
];

function renderThread() {
  harness.state.messages = turn;
  return render(
    <StudioRuntimeProvider>
      <ThreadPrimitive.Root>
        <Conversation />
      </ThreadPrimitive.Root>
    </StudioRuntimeProvider>,
  );
}

describe("Read aloud", () => {
  it("speaks a settled reply and offers to stop", () => {
    renderThread();

    fireEvent.click(screen.getByRole("button", { name: "Read reply aloud" }));

    expect(speech.speak).toHaveBeenCalledWith("Listen to this answer.");
    expect(screen.getByRole("button", { name: "Stop reading" })).toBeInTheDocument();
    const announcements = screen.getAllByRole("status").map((node) => node.textContent);
    expect(announcements).toContain("Reading this reply aloud.");
  });

  it("stops on request", () => {
    renderThread();
    fireEvent.click(screen.getByRole("button", { name: "Read reply aloud" }));

    fireEvent.click(screen.getByRole("button", { name: "Stop reading" }));

    expect(speech.cancel).toHaveBeenCalled();
  });

  it("stops on Escape inside the thread", () => {
    const { container } = renderThread();
    fireEvent.click(screen.getByRole("button", { name: "Read reply aloud" }));

    fireEvent.keyDown(container.querySelector(".aui-thread-root") ?? document.body, {
      key: "Escape",
    });

    expect(speech.cancel).toHaveBeenCalled();
  });

  it("does not offer speech on a reply with no prose", () => {
    harness.state.messages = [
      { id: "u-1", parentId: null, role: "user", content: "Check this bet" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "" },
    ];
    render(
      <StudioRuntimeProvider>
        <ThreadPrimitive.Root>
          <Conversation />
        </ThreadPrimitive.Root>
      </StudioRuntimeProvider>,
    );

    expect(screen.queryByRole("button", { name: "Read reply aloud" })).toBeNull();
  });
});
