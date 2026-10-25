/**
 * What the transcript says out loud.
 *
 * A chat transcript is a poor live region: every streamed token, every
 * re-rendered Markdown block, and every unrelated state change inside it can be
 * announced. The studio instead speaks once per settled turn, and this module
 * turns that turn into something worth hearing: Markdown flattened to prose,
 * no markers, no code fences.
 */

import type { ChatMessage } from "../types";
import { parseMarkdown, type MdBlock, type MdInline } from "./markdown";

function inlineText(spans: MdInline[]): string {
  return spans.map((span) => span.text).join("");
}

function blockText(block: MdBlock): string {
  switch (block.type) {
    case "paragraph":
    case "heading":
    case "quote":
      return inlineText(block.spans);
    case "list":
      return block.items.map((item) => inlineText(item)).join(". ");
    case "code":
      return block.code;
    case "rule":
      return "";
  }
}

/** Markdown as speech: one sentence per block, markers removed. */
export function spokenText(source: string): string {
  return parseMarkdown(source)
    .map(blockText)
    .filter(Boolean)
    .join(". ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * The sentence a settled turn contributes to the live region. Returns null for
 * turns with nothing to say (a card-only reply still has its prose in
 * `content`, and a failed turn is announced by its alert instead).
 */
export function announcementText(message: ChatMessage): string | null {
  if (message.role === "user") {
    return null;
  }
  const prose = spokenText(message.content);
  if (!prose) {
    // A surface-only turn still finished; without a word for it the reader is
    // left with silence and no idea the card is there.
    if (message.parts?.some((part) => part.kind === "ui")) {
      return "Studio posted a card to the transcript.";
    }
    return null;
  }
  return message.role === "notice" ? `Notice: ${prose}` : `Studio replied: ${prose}`;
}
