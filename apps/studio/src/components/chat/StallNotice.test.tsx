import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { ChatMessage } from "../../types";
import { Conversation } from "./Conversation";
import { STALL_THRESHOLD_MS } from "./StallNotice";

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

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const turn: ChatMessage[] = [
  { id: "u-1", parentId: null, role: "user", content: "Check this bet" },
  { id: "a-1", parentId: "u-1", role: "assistant", content: "One sentence, then silence." },
];

function renderRunning() {
  harness.state.messages = turn;
  harness.state.streaming = true;
  return render(
    <StudioRuntimeProvider>
      <Conversation />
    </StudioRuntimeProvider>,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  harness.state.streaming = false;
  vi.useRealTimers();
});

function stallLine(): HTMLElement | null {
  return document.querySelector(".stall__line");
}

/** The notice's own polite region, beside the transcript's phase status. */
function announcement(): string | null {
  const regions = screen
    .getAllByRole("status")
    .map((node) => node.textContent ?? "")
    .filter((text) => text.startsWith("Still working"));
  expect(regions).toHaveLength(1);
  return regions[0];
}

describe("StallNotice", () => {
  it("says it is still working only after real silence", () => {
    renderRunning();

    expect(stallLine()).toBeNull();

    act(() => {
      vi.advanceTimersByTime(STALL_THRESHOLD_MS);
    });

    expect(stallLine()?.textContent).toContain("Still working");
    expect(stallLine()?.textContent).toMatch(/no new output for \d+s/);
  });

  it("disappears the moment the run settles", () => {
    const { rerender } = renderRunning();
    act(() => {
      vi.advanceTimersByTime(STALL_THRESHOLD_MS);
    });
    expect(stallLine()).not.toBeNull();

    harness.state.streaming = false;
    rerender(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    expect(stallLine()).toBeNull();
  });

  it("announces once, not on every tick of the counter", () => {
    renderRunning();
    act(() => {
      vi.advanceTimersByTime(STALL_THRESHOLD_MS);
    });

    const first = announcement();

    act(() => {
      vi.advanceTimersByTime(30_000);
    });

    expect(announcement()).toBe(first);
    // The visible line, meanwhile, keeps counting honestly.
    expect(stallLine()?.textContent).toMatch(/3[0-9]s/);
  });

  it("never claims work on a settled reply", () => {
    harness.state.messages = turn;
    harness.state.streaming = false;
    render(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    act(() => {
      vi.advanceTimersByTime(STALL_THRESHOLD_MS * 3);
    });

    expect(stallLine()).toBeNull();
  });
});
