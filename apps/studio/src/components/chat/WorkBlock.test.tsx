/**
 * The run row (issue #392).
 *
 * A turn does three kinds of things: it thinks, it calls tools, and it answers.
 * The answer is the loud thing; the thinking and the calls are the record of
 * how it got there. These tests pin the four properties that make that work
 * without losing the audit trail: one row per settled run, approvals kept
 * outside it and answerable while it is closed, prose and cards in the agent's
 * order, and a label built from what the turn recorded rather than from prose.
 *
 * The harness is the real one: a mocked Studio store inside a real
 * `StudioRuntimeProvider`, so assistant-ui's grouping and part scopes are the
 * library's own, not a stub.
 */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { ChatMessage, ChatPart } from "../../types";
import { catalogManifest } from "../../ui/catalog";
import { parseUiSpec, type UiNode } from "../../ui/protocol";
import { Conversation } from "./Conversation";

const harness = vi.hoisted(() => ({
  state: {
    messages: [] as unknown[],
    streaming: false,
    thinkingPhase: null as string | null,
    toolActivity: [] as unknown[],
    offlineReplyFor: null as string | null,
    openPanel: vi.fn<(panel: string) => void>(),
    canvas: null,
    regenerateFrom: vi.fn(),
    editFrom: vi.fn(),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn<(approvalId: string, approved: boolean) => Promise<void>>(
      async () => undefined,
    ),
    stopStreaming: vi.fn(),
    sendMessage: vi.fn<(text: string) => Promise<void>>(async () => undefined),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

function call(id: string, name: string, preview = ""): ChatPart {
  return { kind: "tool", id, name, status: "ok", ...(preview ? { preview } : {}) };
}

function pendingWrite(id: string, approvalId: string, prompt: string): ChatPart {
  return {
    kind: "tool",
    id,
    name: "add_job",
    status: "running",
    approval: { id: approvalId, prompt },
  };
}

function outcomeCard(): UiNode {
  const parsed = parseUiSpec(
    {
      type: "outcome-card",
      props: {
        id: "O-1",
        statement: "Minimize the time it takes to propagate secrets",
        importance: 9,
        satisfaction: 3,
      },
    },
    catalogManifest(),
  );
  if (!parsed.ok) {
    throw new Error(parsed.reason);
  }
  return parsed.node;
}

function turn(parts: ChatPart[], content = "The answer."): ChatMessage[] {
  return [{ id: "a-1", parentId: null, role: "assistant", content, parts }];
}

function renderTurn(messages: ChatMessage[]) {
  harness.state.messages = messages;
  return render(
    <StudioRuntimeProvider>
      <Conversation />
    </StudioRuntimeProvider>,
  );
}

const WORKED = turn([
  { kind: "reasoning", text: "Weighing the scored outcomes against the job map." },
  call("c-1", "list_jobs"),
  call("c-2", "get_outcomes", "top bets scored"),
  call("c-3", "update_outcome"),
  { kind: "text", text: "The answer." },
]);

beforeEach(() => {
  harness.state.streaming = false;
  harness.state.thinkingPhase = null;
  harness.state.offlineReplyFor = null;
  harness.state.respondToApproval.mockClear();
});

describe("the run row", () => {
  it("collapses a settled turn's thinking and calls into one row", () => {
    const { container } = renderTurn(WORKED);

    const triggers = container.querySelectorAll(".work-block__trigger");
    expect(triggers).toHaveLength(1);
    const trigger = triggers[0] as HTMLElement;
    expect(trigger.textContent).toMatch(/3 calls/);
    // A turn restored from history carries no timings, so the row must not
    // invent a duration for it.
    expect(trigger.textContent).not.toMatch(/Worked for/);
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    const body = container.querySelector(".work-block__body") as HTMLElement;
    expect(body.hidden).toBe(true);
    const traces = container.querySelectorAll(".tool-trace");
    expect(traces).toHaveLength(3);
    for (const trace of traces) {
      expect(body.contains(trace)).toBe(true);
    }
    expect(body.contains(container.querySelector(".reasoning"))).toBe(true);
  });

  it("shows the recorded work when the row is opened", () => {
    const { container } = renderTurn(WORKED);
    const trigger = container.querySelector(".work-block__trigger") as HTMLElement;
    const body = container.querySelector(".work-block__body") as HTMLElement;

    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(body.hidden).toBe(false);
    expect(body.textContent).toContain("list jobs");
    expect(body.textContent).toContain("update outcome");
    expect(body.textContent).toContain("Weighing the scored outcomes");
  });

  it("labels the row with the calls it holds, never with prose", () => {
    const first = renderTurn(turn([call("c-1", "list_jobs", "top bets scored")]));
    const firstLabel = (
      first.container.querySelector(".work-block__trigger") as HTMLElement
    ).textContent;
    expect(firstLabel).toMatch(/1 call\b/);
    // Neither a tool's own preview nor the reply's prose belongs in the label:
    // it counts records, it does not paraphrase the answer.
    expect(firstLabel).not.toContain("top bets scored");
    expect(firstLabel).not.toContain("The answer");
    first.unmount();

    const second = renderTurn(WORKED);
    const secondLabel = (
      second.container.querySelector(".work-block__trigger") as HTMLElement
    ).textContent;
    expect(secondLabel).toMatch(/3 calls/);
    expect(secondLabel).not.toContain("list jobs");
  });

  it("keeps a pending approval outside the row and answerable while it is closed", async () => {
    const first = renderTurn([
      {
        id: "a-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          call("c-1", "list_jobs"),
          pendingWrite("c-2", "ap-1", "Add the retention job?"),
          { kind: "text", text: "The answer." },
        ],
      },
    ]);

    const body = first.container.querySelector(".work-block__body") as HTMLElement;
    expect(body.hidden).toBe(true);

    const approval = screen.getByRole("group", { name: "Permission needed" });
    expect(body.contains(approval)).toBe(false);
    expect(approval.textContent).toContain("Add the retention job?");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Allow/ }));
    });
    expect(harness.state.respondToApproval.mock.calls[0].slice(0, 2)).toEqual(["ap-1", true]);
    first.unmount();

    // The other half of the question, on a fresh turn: closing the row must not
    // cost the reader the ability to say no.
    harness.state.respondToApproval.mockClear();
    const second = renderTurn([
      {
        id: "a-2",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          call("c-1", "list_jobs"),
          pendingWrite("c-2", "ap-2", "Add the retention job?"),
          { kind: "text", text: "The answer." },
        ],
      },
    ]);
    expect(
      (second.container.querySelector(".work-block__body") as HTMLElement).hidden,
    ).toBe(true);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Don't allow/ }));
    });
    // "Don't allow" opens the optional reason first; the refusal is sent when
    // the person confirms, so the click above records nothing on its own.
    expect(harness.state.respondToApproval).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Send refusal/ }));
    });
    expect(harness.state.respondToApproval.mock.calls[0].slice(0, 2)).toEqual(["ap-2", false]);
  });

  it("groups a call once its approval has been answered", () => {
    const { container } = renderTurn(
      turn([call("c-1", "list_jobs"), call("c-2", "add_job"), { kind: "text", text: "The answer." }]),
    );

    expect(screen.queryByRole("group", { name: "Permission needed" })).toBeNull();
    const body = container.querySelector(".work-block__body") as HTMLElement;
    expect(body.textContent).toContain("add job");
    expect((container.querySelector(".work-block__trigger") as HTMLElement).textContent).toMatch(
      /2 calls/,
    );
  });

  it("keeps prose, then card, then prose in order, with no card in the row", () => {
    const { container } = renderTurn(
      turn([
        { kind: "text", text: "Here is the board." },
        call("c-1", "list_jobs"),
        { kind: "ui", id: "ui-1", node: outcomeCard() },
        { kind: "text", text: "It is the top bet." },
      ]),
    );

    const text = (container.querySelector(".conversation") as HTMLElement).textContent ?? "";
    const intro = text.indexOf("Here is the board.");
    const card = text.indexOf("Minimize the time it takes to propagate secrets");
    const outro = text.indexOf("It is the top bet.");
    expect(intro).toBeGreaterThanOrEqual(0);
    expect(card).toBeGreaterThan(intro);
    expect(outro).toBeGreaterThan(card);

    const body = container.querySelector(".work-block__body") as HTMLElement;
    expect(body.textContent).toContain("list jobs");
    expect(body.textContent).not.toContain("Minimize the time");
  });

  it("announces the turn once, so the row adds no live region of its own", () => {
    const { container } = renderTurn(WORKED);

    // The row exists, and the transcript's own status region stays the single
    // thing that speaks: a second live region would read the work twice.
    expect(container.querySelector(".work-block__trigger")).not.toBeNull();
    expect(
      container.querySelector(".work-block [role='status'], .work-block [aria-live]"),
    ).toBeNull();
  });

  it("opens while the turn runs and closes when it settles", async () => {
    harness.state.streaming = true;
    harness.state.messages = turn([
      { kind: "tool", id: "c-1", name: "list_jobs", status: "running" },
      { kind: "text", text: "The answer." },
    ]);
    const { container, rerender } = render(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    expect(container.querySelector(".work-block__trigger")?.textContent).toMatch(/Working/);
    expect(container.querySelector(".work-block__trigger")).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    harness.state.streaming = false;
    harness.state.messages = turn([call("c-1", "list_jobs"), { kind: "text", text: "The answer." }]);
    rerender(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    const trigger = await screen.findByRole("button", { name: /Worked for \d+s · 1 call/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
