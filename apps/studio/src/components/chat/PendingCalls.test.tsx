/**
 * The pending-call strip (issue #390).
 *
 * While a turn runs, the transcript is the record of what happened; this strip
 * is the one place that answers what has not happened yet. These tests pin the
 * properties that make it honest: only in-flight calls appear, in the
 * transcript's order, with the transcript's own labels; a duration is shown
 * only when the store recorded a start; a settled call leaves the strip; and
 * the strip never becomes a second voice on the page.
 *
 * The harness is the real one — a mocked Studio store inside a real
 * `StudioRuntimeProvider` — so the transcript around the strip is the library's
 * own rendering, not a stub.
 */

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { ChatMessage, ChatPart } from "../../types";
import { Conversation } from "./Conversation";

const harness = vi.hoisted(() => ({
  state: {
    messages: [] as unknown[],
    streaming: true,
    thinkingPhase: null as string | null,
    toolActivity: [] as unknown[],
    offlineReplyFor: null as string | null,
    openPanel: vi.fn<(panel: string) => void>(),
    canvas: null,
    regenerateFrom: vi.fn(),
    editFrom: vi.fn(),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(async () => undefined),
    stopStreaming: vi.fn(),
    sendMessage: vi.fn(async () => undefined),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

function running(id: string, name: string): ChatPart {
  return { kind: "tool", id, name, status: "running" };
}

function settled(id: string, name: string): ChatPart {
  return { kind: "tool", id, name, status: "ok", preview: "done" };
}

function awaiting(id: string, name: string, prompt: string): ChatPart {
  return { kind: "tool", id, name, status: "running", approval: { id: `ap-${id}`, prompt } };
}

function turn(parts: ChatPart[]): ChatMessage[] {
  return [{ id: "a-1", parentId: null, role: "assistant", content: "", parts }];
}

function renderTurn(messages: ChatMessage[]) {
  harness.state.messages = messages;
  return render(
    <StudioRuntimeProvider>
      <Conversation />
    </StudioRuntimeProvider>,
  );
}

beforeEach(() => {
  harness.state.streaming = true;
  harness.state.messages = [];
  harness.state.respondToApproval.mockClear();
});

describe("the pending-call strip", () => {
  it("shows only running and awaiting-approval calls, in transcript order", () => {
    const { container } = renderTurn(
      turn([
        running("c-1", "list_jobs"),
        settled("c-2", "get_outcomes"),
        awaiting("c-3", "add_job", "Add the retention job?"),
      ]),
    );

    const rows = container.querySelectorAll(".pending-calls__row");
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("list jobs");
    expect(rows[1].textContent).toContain("add job");
    // The settled call belongs to the transcript, not here.
    expect(container.querySelector(".pending-calls")?.textContent).not.toContain("get outcomes");
  });

  it("names the count and says which of the two states each row is in", () => {
    const { container } = renderTurn(
      turn([running("c-1", "list_jobs"), awaiting("c-2", "add_job", "Add the retention job?")]),
    );

    expect(container.querySelector(".pending-calls__head")?.textContent).toContain("2 calls");
    const rows = container.querySelectorAll(".pending-calls__row");
    expect(rows[0].textContent).toContain("working");
    expect(rows[1].textContent).toContain("waiting for your answer");
    expect(rows[1].textContent).toContain("Add the retention job?");
  });

  it("shows no duration when the store recorded no start", () => {
    // A part with no `startedAt` — a turn restored from history — must not get
    // a number the store never measured.
    const { container } = renderTurn(turn([running("c-1", "list_jobs")]));

    expect(container.querySelector(".pending-calls__elapsed")).toBeNull();
    expect(container.querySelector(".pending-calls")?.textContent).not.toMatch(/\d+s/);
  });

  it("counts from the store's recorded start when there is one", () => {
    const started = { ...running("c-1", "list_jobs"), startedAt: Date.now() - 3000 } as ChatPart;
    const { container } = renderTurn(turn([started]));

    expect(container.querySelector(".pending-calls__elapsed")?.textContent).toBe("3s");
  });

  it("drops the row the moment the call settles, leaving one location", () => {
    const { container, rerender } = renderTurn(turn([running("c-1", "list_jobs")]));
    expect(container.querySelectorAll(".pending-calls__row")).toHaveLength(1);

    harness.state.messages = turn([settled("c-1", "list_jobs")]);
    rerender(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    // The strip is empty and the transcript now holds the call: exactly one.
    expect(container.querySelectorAll(".pending-calls__row")).toHaveLength(0);
    expect(container.querySelector(".work-block")?.textContent).toContain("list jobs");
  });

  it("is not a live region, so it never speaks over the transcript", () => {
    const { container } = renderTurn(turn([running("c-1", "list_jobs")]));

    const strip = container.querySelector(".pending-calls") as HTMLElement;
    expect(strip.querySelector("[role='status'], [aria-live]")).toBeNull();
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });
});
