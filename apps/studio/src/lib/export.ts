import type { ChatMessage } from "../types";

const SPEAKER: Record<ChatMessage["role"], string> = {
  user: "User",
  assistant: "Assistant",
  notice: "Notice",
};

/**
 * A conversation as Markdown.
 *
 * Threads die with the session, so the export has to stand on its own: every
 * speaker is labelled, prose keeps its Markdown, and an agent-composed surface
 * travels as a fenced JSON block rather than disappearing with the UI that
 * rendered it.
 */
export function conversationToMarkdown(
  messages: ChatMessage[],
  exportedAt: Date = new Date(),
): string {
  const lines: string[] = [
    "# Agentic ODI conversation",
    "",
    `_Exported ${exportedAt.toISOString().slice(0, 10)}._`,
    "",
  ];

  for (const message of messages) {
    lines.push(`## ${SPEAKER[message.role]}`, "");

    if (message.role === "assistant" && message.parts && message.parts.length > 0) {
      for (const part of message.parts) {
        if (part.kind === "text") {
          if (part.text.trim()) {
            lines.push(part.text, "");
          }
          continue;
        }
        lines.push(
          `**Surface: \`${part.node.type}\`**`,
          "",
          "```json",
          JSON.stringify(part.node, null, 2),
          "```",
          "",
        );
      }
    } else if (message.content.trim()) {
      lines.push(message.content, "");
    }

    if (message.error) {
      lines.push(`**Error:** ${message.error.message}`, "");
    }
  }

  return `${lines.join("\n").replace(/\n{3,}/g, "\n\n").trimEnd()}\n`;
}

export function exportFilename(exportedAt: Date = new Date()): string {
  return `agentic-odi-conversation-${exportedAt.toISOString().slice(0, 10)}.md`;
}

/** Hand a Markdown file to the browser's save dialog. */
export function downloadMarkdown(markdown: string, filename: string): void {
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
