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
      const before = lines.length;
      for (const part of message.parts) {
        if (part.kind === "text") {
          if (part.text.trim()) {
            lines.push(part.text, "");
          }
          continue;
        }
        if (part.kind !== "ui") {
          // Reasoning and tool activity are the runtime's own; the transcript
          // carries what the user was shown.
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
      if (lines.length === before && message.content.trim()) {
        lines.push(message.content, "");
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

/**
 * Hand a text file to the browser's save dialog.
 *
 * Every export in the Studio ends here. The URL is released on the next tick rather
 * than in the same turn as the click, so the browser has taken the blob before it
 * disappears.
 */
export function downloadFile(text: string, filename: string, mime: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** Hand a Markdown file to the browser's save dialog. */
export function downloadMarkdown(markdown: string, filename: string): void {
  downloadFile(markdown, filename, "text/markdown;charset=utf-8");
}
