import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "../types";
import { catalogManifest } from "../ui/catalog";
import { parseUiSpec, type UiNode } from "../ui/protocol";
import {
  conversationToMarkdown,
  downloadFile,
  downloadMarkdown,
  exportFilename,
} from "./export";

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
      { id: "m-1", parentId: null, role: "user", content: "Show me the top outcomes." },
      { id: "m-2", parentId: "m-1", role: "assistant", content: "Here they are." },
      { id: "m-3", parentId: "m-2", role: "notice", content: "Local guidance only." },
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
        id: "m-1",
        parentId: null,
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
      { id: "m-1", parentId: null, role: "assistant", content: "Plain **answer**." },
    ];

    expect(conversationToMarkdown(messages, exportedAt)).toContain("Plain **answer**.");
  });

  it("dates the export in the filename", () => {
    expect(exportFilename(exportedAt)).toBe("agentic-odi-conversation-2026-10-24.md");
  });
});

describe("downloadFile", () => {
  let createObjectURL: ReturnType<typeof vi.fn>;
  let revokeObjectURL: ReturnType<typeof vi.fn>;
  let click: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    createObjectURL = vi.fn(() => "blob:export");
    revokeObjectURL = vi.fn();
    Object.defineProperty(window, "URL", {
      value: { ...window.URL, createObjectURL, revokeObjectURL },
      configurable: true,
    });
    click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  async function released() {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  it("hands the text over under the name and type the caller asks for", async () => {
    downloadFile("Name\r\nJobs", "table.csv", "text/csv;charset=utf-8");

    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("text/csv;charset=utf-8");
    expect(await blob.text()).toBe("Name\r\nJobs");
    const anchor = click.mock.contexts[0] as HTMLAnchorElement;
    expect(anchor.download).toBe("table.csv");
    expect(anchor.isConnected).toBe(false);

    await released();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:export");
  });

  // Two surfaces already hand-rolled this dance. One behaviour means one function, so the
  // Markdown export the bar has always done now goes through the same door.
  it("is the download that downloadMarkdown performs", async () => {
    downloadMarkdown("# thread", "agentic-odi-conversation-2026-10-24.md");

    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("text/markdown;charset=utf-8");
    expect(await blob.text()).toBe("# thread");
    const anchor = click.mock.contexts[0] as HTMLAnchorElement;
    expect(anchor.download).toBe("agentic-odi-conversation-2026-10-24.md");
  });
});
