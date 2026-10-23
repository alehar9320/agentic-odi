import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "../../types";
import { catalogManifest } from "../../ui/catalog";
import { parseUiSpec, type UiNode } from "../../ui/protocol";
import { Conversation } from "./Conversation";

const harness = vi.hoisted(() => ({
  state: {
    messages: [] as unknown[],
    streaming: false,
    thinkingPhase: null as string | null,
    toolActivity: [] as unknown[],
    offlineReply: false,
    sendMessage: vi.fn<(text: string) => Promise<void>>(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

function nodeOf(spec: unknown): UiNode {
  const parsed = parseUiSpec(spec, catalogManifest());
  if (!parsed.ok) {
    throw new Error(parsed.reason);
  }
  return parsed.node;
}

function outcomeCard(actions = false): UiNode {
  return nodeOf({
    type: "outcome-card",
    props: {
      id: "O-1",
      statement: "Minimize the time it takes to propagate secrets",
      importance: 9,
      satisfaction: 3,
      ...(actions
        ? {
            actions: [
              { label: "Simulate this bet", intent: "Simulate O-1", tone: "primary" },
              { label: "Find evidence", intent: "Find evidence for O-1", tone: "ghost" },
            ],
          }
        : {}),
    },
  });
}

function renderTurn(messages: ChatMessage[]) {
  harness.state.messages = messages;
  return render(<Conversation />);
}

describe("Conversation", () => {
  it("renders prose and surfaces in the agent's order", () => {
    const { container } = renderTurn([
      {
        role: "assistant",
        content: "Here is the board. It is the top bet.",
        parts: [
          { kind: "text", text: "Here is the board." },
          { kind: "ui", id: "ui-1", node: outcomeCard() },
          { kind: "text", text: "It is the top bet." },
        ],
      },
    ]);

    const text = container.textContent ?? "";
    const intro = text.indexOf("Here is the board.");
    const card = text.indexOf("Minimize the time it takes to propagate secrets");
    const outro = text.indexOf("It is the top bet.");

    expect(intro).toBeGreaterThanOrEqual(0);
    expect(card).toBeGreaterThan(intro);
    expect(outro).toBeGreaterThan(card);
  });

  it("keeps history without parts readable", () => {
    const { container } = renderTurn([
      { role: "assistant", content: "**Scored** three outcomes." },
    ]);

    expect(container.textContent).toContain("Scored");
    expect(container.querySelector("strong")).not.toBeNull();
  });

  it("renders a surface-only turn", () => {
    const { container } = renderTurn([
      { role: "assistant", content: "", parts: [{ kind: "ui", id: "ui-1", node: outcomeCard() }] },
    ]);

    expect(container.textContent).toContain("Minimize the time it takes to propagate secrets");
  });

  it("turns a card action into the user's next message", () => {
    harness.state.sendMessage = vi.fn<(text: string) => Promise<void>>();
    renderTurn([
      {
        role: "assistant",
        content: "",
        parts: [{ kind: "ui", id: "ui-1", node: outcomeCard(true) }],
      },
    ]);

    fireEvent.click(document.querySelector("button.ui-action") as HTMLButtonElement);

    expect(harness.state.sendMessage).toHaveBeenCalledWith("Simulate O-1");
  });
});
