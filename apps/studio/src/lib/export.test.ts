import { describe, expect, it } from "vitest";

import type { ChatMessage } from "../types";
import { catalogManifest } from "../ui/catalog";
import { parseUiSpec, type UiNode } from "../ui/protocol";
import { conversationToMarkdown, exportFilename } from "./export";

const exportedAt = new Date("2026-10-24T12:00:00Z");

function surfaceCard(): UiNode {
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

describe("conversationToMarkdown", () => {
  it("labels every speaker", () => {
    const messages: ChatMessage[] = [
      { role: "user", content: "Show me the top outcomes." },
      { role: "assistant", content: "Here they are." },
      { role: "notice", content: "Local guidance only." },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown).toContain("## User");
    expect(markdown).toContain("## Assistant");
    expect(markdown).toContain("## Notice");
    expect(markdown).toContain("Show me the top outcomes.");
    expect(markdown).toContain("Local guidance only.");
  });

  it("keeps an inline surface as a fenced JSON block", () => {
    const messages: ChatMessage[] = [
      {
        role: "assistant",
        content: "",
        parts: [
          { kind: "text", text: "Here is the card." },
          { kind: "ui", id: "ui-1", node: surfaceCard() },
        ],
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown).toContain("```json");
    expect(markdown).toContain('"type": "outcome-card"');
    expect(markdown).toContain("Minimize the time it takes to propagate secrets");
  });

  it("uses the combined prose when a turn has no parts", () => {
    const messages: ChatMessage[] = [
      { role: "assistant", content: "Plain **answer**." },
    ];

    expect(conversationToMarkdown(messages, exportedAt)).toContain("Plain **answer**.");
  });

  it("dates the export in the filename", () => {
    expect(exportFilename(exportedAt)).toBe("agentic-odi-conversation-2026-10-24.md");
  });
});
