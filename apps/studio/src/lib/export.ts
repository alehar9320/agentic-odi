import {
  buildClaimBlocks,
  hideMarkers,
  type ClaimBlock,
  type ClaimSegment,
} from "../assistant/claims";
import type { ChatMessage, Claim, ClaimCitation } from "../types";

const SPEAKER: Record<ChatMessage["role"], string> = {
  user: "User",
  assistant: "Assistant",
  notice: "Notice",
};

/** `Source · record name, record id`, built only from fields the reply holds. */
function recordLabel(citation: ClaimCitation): string {
  const name =
    citation.source_name && citation.name
      ? `${citation.source_name} · ${citation.name}`
      : citation.name || citation.source_name;
  if (name && citation.id) {
    return `${name}, record ${citation.id}`;
  }
  return name || (citation.id ? `record ${citation.id}` : "");
}

/** The same three distinctions the transcript draws, in the same words. */
function claimSuffix(claim: Claim): string {
  if (claim.status === "hypothesis") {
    return " (Hypothesis)";
  }
  if (claim.status === "uncited") {
    return " (Uncited)";
  }
  const records = claim.evidence.map(recordLabel).filter(Boolean);
  if (records.length === 0) {
    return " (cited, no record named)";
  }
  return ` (per ${records.join("; ")})`;
}

function segmentText(segment: ClaimSegment): string {
  if (!segment.claim) {
    return segment.text;
  }
  return `${segment.text}${claimSuffix(segment.claim)}`;
}

/** One parsed block, written back as the Markdown the transcript rendered. */
function blockLines(block: ClaimBlock): string[] {
  const items = block.items.map((item) => item.map(segmentText).join(""));
  if (block.kind === "code") {
    return ["```", ...items, "```", ""];
  }
  if (block.kind === "heading") {
    return [...items.map((item) => `### ${item.trim()}`), ""];
  }
  if (block.kind === "list") {
    return [...items.map((item) => `- ${item.trim()}`), ""];
  }
  return [...items.map((item) => item.trim()), ""];
}

/**
 * A claim-bearing reply, with every sentence carrying what it carried on screen.
 *
 * The prose arrives as syntax: markers around nothing a reader should see, and a
 * validated claim list beside it. `buildClaimBlocks` is the parser the transcript
 * itself uses, so the file cannot drift from what the person read.
 */
function claimsLines(content: string, claims: Claim[]): string[] {
  const blocks = buildClaimBlocks(content, claims);
  const emitted = new Set<number>();
  const lines: string[] = [];
  for (const block of blocks) {
    for (const item of block.items) {
      for (const segment of item) {
        if (segment.claim) {
          emitted.add(segment.claim.index);
        }
      }
    }
    lines.push(...blockLines(block));
  }
  // A claim the prose does not contain still has to reach the file. Losing an
  // answer is the failure this export exists to fix, so it travels as its own
  // line rather than vanishing with the sentence it could not be matched to —
  // but a sentence already on the page is not printed twice over a label that
  // would not attach.
  const printed = lines.join(" ").replace(/\s+/g, " ");
  for (const claim of claims) {
    if (emitted.has(claim.index)) {
      continue;
    }
    const sentence = claim.text
      .replace(/\s+/g, " ")
      .replace(/[.!?]+$/, "")
      .trim();
    if (sentence && printed.includes(sentence)) {
      continue;
    }
    lines.push(`${claim.text}${claimSuffix(claim)}`, "");
  }
  return lines;
}

/**
 * A conversation as Markdown.
 *
 * Threads die with the session, so the export has to stand on its own: every
 * speaker is labelled, prose keeps its Markdown, a cited sentence keeps its
 * citation, and an agent-composed surface travels as a fenced JSON block rather
 * than disappearing with the UI that rendered it.
 */
export function conversationToMarkdown(
  messages: ChatMessage[],
  exportedAt: Date = new Date(),
): string {
  const cites = messages.some((message) =>
    (message.parts ?? []).some((part) => part.kind === "claims"),
  );
  const lines: string[] = [
    "# Agentic ODI conversation",
    "",
    `_Exported ${exportedAt.toISOString().slice(0, 10)}._`,
    "",
  ];
  if (cites) {
    // A label is a snapshot of what the turn read, not a promise that the
    // record is still in the studio.
    lines.push(
      "_Citation labels name the record as it stood when the reply was written._",
      "",
    );
  }

  for (const message of messages) {
    lines.push(`## ${SPEAKER[message.role]}`, "");

    if (
      message.role === "assistant" &&
      message.parts &&
      message.parts.length > 0
    ) {
      const before = lines.length;
      const claimProse = new Set<string>();
      for (const part of message.parts) {
        if (part.kind === "claims") {
          claimProse.add(hideMarkers(part.content).trim());
        }
      }
      for (const part of message.parts) {
        if (part.kind === "text") {
          // Markers are syntax, and the finished claim list replaces the prose
          // it was streamed with — printing both would say the same thing twice.
          const prose = hideMarkers(part.text);
          if (prose.trim() && !claimProse.has(prose.trim())) {
            lines.push(prose, "");
          }
          continue;
        }
        if (part.kind === "claims") {
          lines.push(...claimsLines(part.content, part.claims));
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
        lines.push(hideMarkers(message.content), "");
      }
    } else if (message.content.trim()) {
      lines.push(message.content, "");
    }

    if (message.error) {
      lines.push(`**Error:** ${message.error.message}`, "");
    }
  }

  return `${lines
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd()}\n`;
}

export function exportFilename(exportedAt: Date = new Date()): string {
  return `agentic-odi-conversation-${exportedAt.toISOString().slice(0, 10)}.md`;
}

/** Hand a file to the browser's save dialog. */
function downloadFile(content: string, filename: string, type: string): void {
  const blob = new Blob([content], { type: `${type};charset=utf-8` });
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

export function downloadMarkdown(markdown: string, filename: string): void {
  downloadFile(markdown, filename, "text/markdown");
}

export function downloadJson(json: string, filename: string): void {
  downloadFile(json, filename, "application/json");
}

export function workspaceExportFilename(exportedAt: Date = new Date()): string {
  return `agentic-odi-workspace-${exportedAt.toISOString().slice(0, 10)}.json`;
}
